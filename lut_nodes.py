import os
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Dict, Optional, Tuple

import torch

from .lut_cube import CubeLUT, load_cube

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


def _find_ffmpeg() -> str:
    forced = os.environ.get("VHS_FORCE_FFMPEG_PATH") or os.environ.get("FFMPEG_PATH")
    candidates = [forced] if forced else []
    try:
        import imageio_ffmpeg
        candidates.append(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        pass
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        candidates.append(system_ffmpeg)
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate
    raise FileNotFoundError(
        "FFmpeg를 찾을 수 없습니다. imageio-ffmpeg를 설치하거나 FFmpeg 경로를 PATH, "
        "FFMPEG_PATH 또는 VHS_FORCE_FFMPEG_PATH에 지정하세요."
    )


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


def _output_paths(filename_prefix: str, extension: str, save_output: bool) -> Tuple[str, str]:
    if folder_paths is None:
        base_dir = os.path.join(os.getcwd(), "output" if save_output else "temp")
        os.makedirs(base_dir, exist_ok=True)
        safe_prefix = filename_prefix or "LUTVideo"
        return base_dir, os.path.join(base_dir, f"{safe_prefix}_00001{extension}")

    output_dir = folder_paths.get_output_directory() if save_output else folder_paths.get_temp_directory()
    full_folder, filename, counter, _, _ = folder_paths.get_save_image_path(filename_prefix or "LUTVideo", output_dir)
    os.makedirs(full_folder, exist_ok=True)
    path = os.path.join(full_folder, f"{filename}_{counter:05d}{extension}")
    while os.path.exists(path):
        counter += 1
        path = os.path.join(full_folder, f"{filename}_{counter:05d}{extension}")
    return full_folder, path


def _codec_args(codec: str, quality: int) -> Tuple[str, str, list]:
    if codec == "h264_high":
        return ".mp4", "h264", ["-c:v", "libx264", "-preset", "medium", "-crf", str(quality), "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    if codec == "h264_lossless":
        return ".mkv", "h264_lossless", ["-c:v", "libx264rgb", "-preset", "medium", "-qp", "0", "-pix_fmt", "rgb24"]
    if codec == "prores_4444":
        return ".mov", "prores_4444", ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuv444p10le"]
    if codec == "ffv1_lossless":
        return ".mkv", "ffv1_lossless", ["-c:v", "ffv1", "-level", "3", "-coder", "1", "-context", "1", "-g", "1", "-pix_fmt", "rgb24"]
    raise ValueError(f"지원하지 않는 코덱: {codec}")


def _preview_format(codec: str) -> str:
    return {
        "h264_high": "video/h264-mp4",
        "h264_lossless": "video/h264-mkv",
        "prores_4444": "video/prores-mov",
        "ffv1_lossless": "video/ffv1-mkv",
    }.get(codec, "video/mp4")


def _preview_payload(path: str, save_output: bool, frame_rate: float, codec: str) -> dict:
    if folder_paths is None:
        base_dir = os.path.dirname(path)
    else:
        base_dir = folder_paths.get_output_directory() if save_output else folder_paths.get_temp_directory()
    subfolder = os.path.relpath(os.path.dirname(path), base_dir).replace("\\", "/")
    if subfolder == ".":
        subfolder = ""
    return {
        "filename": os.path.basename(path),
        "subfolder": subfolder,
        "type": "output" if save_output else "temp",
        "format": _preview_format(codec),
        "frame_rate": float(frame_rate),
        "fullpath": path,
    }


def _audio_wave_path(audio: Dict, directory: str) -> Optional[str]:
    if not isinstance(audio, dict) or "waveform" not in audio or "sample_rate" not in audio:
        return None
    waveform = audio["waveform"]
    if not isinstance(waveform, torch.Tensor) or waveform.numel() == 0:
        return None
    if waveform.ndim == 2:
        waveform = waveform.unsqueeze(0)
    channels = int(waveform.shape[1])
    samples = waveform.squeeze(0).transpose(0, 1).contiguous().detach().cpu().float()
    path = os.path.join(directory, "lut_audio_" + next(tempfile._get_candidate_names()) + ".wav")
    with wave.open(path, "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(4)
        handle.setframerate(int(audio["sample_rate"]))
        handle.writeframes(samples.numpy().tobytes())
    return path


class LUTVideoSave:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "lut_file": (_lut_choices(), {
                    "tooltip": "ComfyUI/models/luts에 넣은 Premiere/CapCut 호환 .cube LUT를 선택하세요.",
                }),
                "frame_rate": ("FLOAT", {"default": 24.0, "min": 1.0, "max": 240.0, "step": 0.01}),
                "filename_prefix": ("STRING", {"default": "LUTVideo"}),
                "codec": (["h264_high", "h264_lossless", "prores_4444", "ffv1_lossless"], {"default": "h264_high"}),
                "quality": ("INT", {"default": 14, "min": 0, "max": 51, "step": 1, "tooltip": "H.264 고화질 모드의 CRF입니다. 낮을수록 고화질입니다."}),
                "lut_strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "frame_chunk": ("INT", {"default": 4, "min": 1, "max": 64, "step": 1}),
                "save_output": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "audio": ("AUDIO",),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("video_path",)
    FUNCTION = "save_video"
    OUTPUT_NODE = True
    CATEGORY = "Flagship Melona/LUT"

    def save_video(
        self,
        images,
        lut_file,
        frame_rate,
        filename_prefix,
        codec,
        quality,
        lut_strength,
        frame_chunk,
        save_output,
        audio=None,
    ):
        if not isinstance(images, torch.Tensor) or images.ndim != 4:
            raise ValueError("images는 [frames, height, width, channels] 형태의 IMAGE 배치여야 합니다.")
        if images.shape[-1] not in (3, 4):
            raise ValueError("RGB 또는 RGBA 이미지 입력만 지원합니다.")
        if len(images) == 0:
            raise ValueError("저장할 영상 프레임이 없습니다.")

        lut_path = _resolve_lut_path(lut_file)
        lut: Optional[CubeLUT] = load_cube(lut_path) if float(lut_strength) < 0.999999 else None
        ffmpeg = _find_ffmpeg()
        extension, _codec_name, codec_args = _codec_args(codec, int(quality))
        _folder, final_path = _output_paths(filename_prefix, extension, bool(save_output))
        temp_video = final_path
        temp_audio = None
        temp_dir = folder_paths.get_temp_directory() if folder_paths is not None else tempfile.gettempdir()
        if audio is not None:
            temp_video = os.path.join(temp_dir, Path(final_path).stem + ".video" + extension)
            temp_audio = _audio_wave_path(audio, temp_dir)

        height, width = int(images.shape[1]), int(images.shape[2])
        channels = int(images.shape[3])
        pixel_format = "rgba" if channels == 4 else "rgb24"
        input_format = "rgba" if channels == 4 else "rgb24"
        lut_filter = None
        if lut is None:
            escaped_lut_path = lut_path.replace("\\", "/").replace(":", "\\:")
            lut_filter = f"lut3d=file='{escaped_lut_path}':interp=trilinear"
        args = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "rawvideo", "-pix_fmt", input_format,
            "-s", f"{width}x{height}", "-r", str(float(frame_rate)), "-i", "-",
            "-an", "-color_range", "pc", "-colorspace", "bt709",
            "-color_primaries", "bt709", "-color_trc", "bt709",
        ] + codec_args + ["-r", str(float(frame_rate)), temp_video]
        if lut_filter is not None:
            args[args.index("-an") + 1:args.index("-an") + 1] = ["-vf", lut_filter]
        del pixel_format

        process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            for start in range(0, int(images.shape[0]), max(1, int(frame_chunk))):
                chunk = images[start:start + int(frame_chunk)]
                rgb = chunk[..., :3]
                if lut is None:
                    graded = rgb.to(dtype=torch.float32)
                else:
                    graded = lut.apply(rgb)
                if lut is not None and lut_strength < 1.0:
                    graded = torch.lerp(rgb.to(dtype=torch.float32), graded, float(lut_strength))
                if channels == 4:
                    graded = torch.cat((graded, chunk[..., 3:4].to(dtype=torch.float32).clamp(0.0, 1.0)), dim=-1)
                data = (graded.clamp(0.0, 1.0) * 255.0).round().to(torch.uint8).cpu().contiguous().numpy().tobytes()
                process.stdin.write(data)
            process.stdin.close()
            stderr = process.stderr.read().decode("utf-8", errors="replace")
            return_code = process.wait()
        except Exception:
            if process.stdin:
                process.stdin.close()
            process.kill()
            process.wait()
            raise
        if return_code != 0:
            raise RuntimeError(f"FFmpeg 영상 인코딩 실패:\n{stderr}")

        if temp_audio is not None:
            mux_args = [
                ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                "-i", temp_video, "-i", temp_audio,
                "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k", "-shortest", final_path,
            ]
            mux = subprocess.run(mux_args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False)
            if mux.returncode != 0:
                raise RuntimeError("FFmpeg 오디오 결합 실패:\n" + mux.stderr.decode("utf-8", errors="replace"))
            for path in (temp_video, temp_audio):
                try:
                    os.remove(path)
                except OSError:
                    pass

        preview = _preview_payload(final_path, bool(save_output), float(frame_rate), codec)
        preview.update({
            "width": width,
            "height": height,
            "frame_count": int(images.shape[0]),
            "has_audio": temp_audio is not None,
        })
        return {
            "ui": {
                "gifs": [preview],
                "lut_video_preview": [preview],
            },
            "result": (final_path,),
        }


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
    "LUTVideoSave": LUTVideoSave,
    "ApplyLUTToVideoFrames": ApplyLUTToVideoFrames,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LUTVideoSave": "Save Video with LUT",
    "ApplyLUTToVideoFrames": "Apply LUT to Video Frames",
}

