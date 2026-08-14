"""Small utility nodes used by the shared MiniMax H3 workflow."""

from __future__ import annotations

import os

import numpy as np
import torch

import folder_paths
from comfy import model_management


_DETECTOR_CACHE = {}


def _detector_list():
    names = []
    for key in ("ultralytics_bbox", "ultralytics"):
        try:
            names.extend(folder_paths.get_filename_list(key))
        except Exception:
            pass
    unique = []
    seen = set()
    for name in names:
        if name not in seen:
            seen.add(name)
            unique.append(name)
    return unique or ["face_yolov8m.pt"]


def _detector_path(name):
    for key in ("ultralytics_bbox", "ultralytics"):
        try:
            path = folder_paths.get_full_path(key, name)
        except Exception:
            path = None
        if path:
            return path
    for subfolder in ("ultralytics/bbox", "ultralytics", "ultralytics/segm"):
        path = os.path.join(folder_paths.models_dir, *subfolder.split("/"), name)
        if os.path.isfile(path):
            return path
    raise FileNotFoundError(
        f"Face detector '{name}' was not found. Put it in models/ultralytics/bbox/."
    )


def _load_detector(name):
    if name not in _DETECTOR_CACHE:
        from ultralytics import YOLO

        _DETECTOR_CACHE[name] = YOLO(_detector_path(name))
    return _DETECTOR_CACHE[name]


def _to_bgr_u8(frame):
    rgb = (
        frame.detach().float().clamp(0, 1).mul(255).round().byte().cpu().numpy()
    )
    return np.ascontiguousarray(rgb[..., ::-1])


class H3FacePresence:
    """Detect a face before a lazy FaceRefine branch."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "detector": (_detector_list(),),
                "confidence": (
                    "FLOAT",
                    {"default": 0.35, "min": 0.05, "max": 0.95, "step": 0.05},
                ),
            }
        }

    RETURN_TYPES = ("BOOLEAN", "STRING")
    RETURN_NAMES = ("face_found", "report")
    FUNCTION = "detect"
    CATEGORY = "Flagship Melona/H3"

    def detect(self, images, detector, confidence):
        model = _load_detector(detector)
        frame_count = int(images.shape[0])
        for index in range(frame_count):
            model_management.throw_exception_if_processing_interrupted()
            result = model.predict(
                _to_bgr_u8(images[index]), conf=float(confidence), verbose=False
            )[0]
            if len(result.boxes):
                return (
                    True,
                    f"Face found at frame {index + 1}/{frame_count}; FaceRefine enabled.",
                )
        return (
            False,
            f"No face found in {frame_count} frames; original clip passes through.",
        )


class ColorMatchLABChunked:
    """Reinhard Lab color matching without moving a full video batch to VRAM."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_target": ("IMAGE",),
                "image_ref": ("IMAGE",),
                "strength": (
                    "FLOAT",
                    {"default": 0.30, "min": 0.0, "max": 1.0, "step": 0.01},
                ),
                "chunk_size": (
                    "INT",
                    {"default": 2, "min": 1, "max": 32, "step": 1},
                ),
                "free_vram_first": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "match"
    CATEGORY = "Flagship Melona/H3"

    def match(self, image_target, image_ref, strength, chunk_size, free_vram_first):
        if float(strength) == 0 or image_target.shape[0] == 0:
            return (image_target,)

        import kornia

        if free_vram_first:
            model_management.unload_all_models()
            model_management.soft_empty_cache(force=True)

        device = model_management.get_torch_device()
        batch_size = int(image_target.shape[0])
        chunk_size = max(1, min(int(chunk_size), batch_size))
        output = torch.empty_like(image_target, device="cpu", dtype=torch.float32)
        single_ref = image_ref.shape[0] == 1
        ref_std_one = ref_mean_one = None

        if single_ref:
            ref = image_ref[:1].to(device=device, dtype=torch.float32)
            ref = ref.permute(0, 3, 1, 2).contiguous()
            ref_lab = kornia.color.rgb_to_lab(ref)
            ref_std_one, ref_mean_one = torch.std_mean(
                ref_lab.flatten(2), dim=-1, keepdim=True, unbiased=False
            )
            del ref, ref_lab

        for start in range(0, batch_size, chunk_size):
            model_management.throw_exception_if_processing_interrupted()
            end = min(start + chunk_size, batch_size)
            src = image_target[start:end].to(device=device, dtype=torch.float32)
            src = src.permute(0, 3, 1, 2).contiguous()
            src_lab = kornia.color.rgb_to_lab(src)
            src_flat = src_lab.flatten(2)
            src_std, src_mean = torch.std_mean(
                src_flat, dim=-1, keepdim=True, unbiased=False
            )
            src_std = src_std.clamp_min_(1e-6)

            if single_ref:
                ref_mean = ref_mean_one.expand(end - start, -1, -1)
                ref_std = ref_std_one.expand(end - start, -1, -1)
            else:
                ref = image_ref[start:end].to(device=device, dtype=torch.float32)
                ref = ref.permute(0, 3, 1, 2).contiguous()
                ref_lab = kornia.color.rgb_to_lab(ref)
                ref_std, ref_mean = torch.std_mean(
                    ref_lab.flatten(2), dim=-1, keepdim=True, unbiased=False
                )

            corrected_flat = (src_flat - src_mean) * (ref_std / src_std) + ref_mean
            corrected_lab = corrected_flat.view_as(src_lab)
            corrected = kornia.color.lab_to_rgb(corrected_lab)
            corrected = (1.0 - float(strength)) * src + float(strength) * corrected
            corrected = corrected.permute(0, 2, 3, 1).contiguous()
            output[start:end].copy_(corrected.detach().cpu().clamp_(0, 1))

            del src, src_lab, src_flat, src_std, src_mean
            del corrected_flat, corrected_lab, corrected
            if not single_ref:
                del ref, ref_lab, ref_std, ref_mean

        if single_ref:
            del ref_std_one, ref_mean_one
        model_management.soft_empty_cache()
        return (output,)


NODE_CLASS_MAPPINGS = {
    "H3FacePresence": H3FacePresence,
    "ColorMatchLABChunked": ColorMatchLABChunked,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3FacePresence": "H3 Face Presence — Auto Bypass",
    "ColorMatchLABChunked": "Color Match LAB — Chunked (VRAM Safe)",
}
