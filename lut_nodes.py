import os
from pathlib import Path

import torch

from .lut_cube import load_cube

try:
    import folder_paths
except ImportError:  # Allows the LUT parser to be tested outside ComfyUI.
    folder_paths = None


def _register_lut_folder() -> None:
    if folder_paths is None:
        return
    lut_dir = os.path.join(folder_paths.models_dir, "luts")
    os.makedirs(lut_dir, exist_ok=True)
    if hasattr(folder_paths, "add_model_folder_path"):
        if "luts" not in getattr(folder_paths, "folder_names_and_paths", {}):
            folder_paths.add_model_folder_path("luts", lut_dir)
    elif "luts" not in getattr(folder_paths, "folder_names_and_paths", {}):
        extensions = getattr(folder_paths, "supported_pt_extensions", set())
        folder_paths.folder_names_and_paths["luts"] = ([lut_dir], extensions)


def _resolve_lut_path(value: str) -> str:
    raw = os.path.expandvars(os.path.expanduser((value or "").strip().strip('"')))
    if not raw:
        raise ValueError("LUT 파일을 지정하세요.")
    candidates = [raw]
    if folder_paths is not None:
        if raw.replace("\\", "/").lower().startswith("luts/"):
            candidates.insert(0, folder_paths.get_full_path("luts", raw.replace("\\", "/")[5:]))
        candidates.extend([
            os.path.join(folder_paths.models_dir, "luts", raw),
            os.path.join(folder_paths.get_input_directory(), raw),
        ])
    candidates.extend([
        os.path.join(os.getcwd(), raw),
        os.path.join(os.path.dirname(__file__), "luts", raw),
    ])
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            suffix = Path(candidate).suffix.lower()
            if suffix != ".cube":
                raise ValueError("현재 LUT는 .cube 형식만 지원합니다.")
            return os.path.abspath(candidate)
    raise FileNotFoundError(f"LUT 파일을 찾을 수 없습니다: {raw}")


def _lut_choices():
    if folder_paths is not None:
        try:
            choices = [name for name in folder_paths.get_filename_list("luts") if name.lower().endswith(".cube")]
            if choices:
                return choices
        except Exception:
            pass
    return ["(models/luts에 .cube 파일을 넣으세요)"]


class ApplyLUTToVideoFrames:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "lut_file": (_lut_choices(), {
                    "tooltip": "ComfyUI/models/luts에 넣은 Premiere/CapCut 호환 .cube LUT를 선택하세요.",
                }),
                "lut_strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "frame_chunk": ("INT", {"default": 4, "min": 1, "max": 64, "step": 1}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "apply_lut"
    CATEGORY = "Flagship Melona/LUT"

    def apply_lut(self, images, lut_file, lut_strength, frame_chunk):
        if not isinstance(images, torch.Tensor) or images.ndim != 4:
            raise ValueError("images는 [frames, height, width, channels] 형태의 IMAGE 배치여야 합니다.")
        if images.shape[-1] not in (3, 4):
            raise ValueError("RGB 또는 RGBA 이미지 입력만 지원합니다.")
        lut = load_cube(_resolve_lut_path(lut_file))
        output = torch.empty_like(images, dtype=torch.float32)
        chunk_size = max(1, int(frame_chunk))
        for start in range(0, int(images.shape[0]), chunk_size):
            chunk = images[start:start + chunk_size]
            rgb = chunk[..., :3].to(dtype=torch.float32)
            graded = lut.apply(rgb)
            graded = torch.lerp(rgb, graded, float(lut_strength))
            if images.shape[-1] == 4:
                graded = torch.cat((graded, chunk[..., 3:4].to(dtype=torch.float32).clamp(0.0, 1.0)), dim=-1)
            output[start:start + chunk.shape[0]] = graded
        return (output.clamp(0.0, 1.0),)


_register_lut_folder()

NODE_CLASS_MAPPINGS = {
    "ApplyLUTToVideoFrames": ApplyLUTToVideoFrames,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ApplyLUTToVideoFrames": "Apply LUT to Video Frames",
}
