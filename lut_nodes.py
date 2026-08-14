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
    full_folder, filename, cou…4434 tokens truncated…아래 모듈이 없는 경우 ComfyUI가 실제로 사용하는 Python에서 누락된 것만 설치하세요.

- `H3FacePresence`: `ultralytics`
- `ColorMatchLABChunked`: `torch`, `kornia`
- `H3DynamicResonanceSuppressor`: `torch`, `torchaudio`
- LUT 노드: `torch`; 영상 저장 기능은 FFmpeg 필요

## 선택형 연동 노드

`H3FacePresence`를 FaceRefine 자동 우회용으로 쓸 때는 [ComfyUI-H3-FaceRefine](https://github.com/Carasibana/ComfyUI-H3-FaceRefine)과 Boolean에 따라 실제 실행 경로를 늦게 선택하는 Lazy Switch 노드가 필요할 수 있습니다. 이들은 Melona Pack의 필수 종속성이 아니며 자동 설치하지 않습니다.

설치 도우미가 읽을 수 있는 최소 구성 정보는 [`INSTALL_MANIFEST.json`](INSTALL_MANIFEST.json)에 정리되어 있습니다.

## 얼굴 검출 모델

얼굴 검출 모델:

```text
ComfyUI/models/ultralytics/bbox/face_yolov8m.pt
```

다운로드: [Bingsu/adetailer — face_yolov8m.pt](https://huggingface.co/Bingsu/adetailer/blob/main/face_yolov8m.pt)

다른 H3 모델과 입력 파일은 이 저장소에서 다운로드하거나 재배포하지 않습니다.

## 설치 검증

저장소가 `ComfyUI/custom_nodes/ComfyUI-Flagship-Melona-Pack`에 설치된 상태에서 ComfyUI가 사용하는 Python으로 실행합니다.

```bash
python verify_install.py --comfy-root /path/to/ComfyUI
```

Windows Portable 예시:

```powershell
E:\ComfyUI_portable\python_embeded\python.exe verify_install.py --comfy-root E:\ComfyUI_portable\ComfyUI
```

검증기는 다섯 Melona 노드, FaceRefine, NativeAudioLock, 이전 분리형 폴더 충돌과 얼굴 검출 모델을 확인합니다.

## 문제 해결

### 긴 영상 최종 색상 보정에서 OOM

- `chunk_size=2` 사용
- 여전히 부족하면 `chunk_size=1`
- `free_vram_first=true` 유지

단순 VRAM Clean만으로는 전체 영상 배치가 다시 GPU에 올라가는 문제를 해결하지 못합니다.

### 얼굴이 없는 장면에서 FaceRefine 중단

`H3FacePresence`의 Boolean 출력을 `LazySwitchKJ`에 연결합니다. `false` 입력에는 원본 프레임, `true` 입력에는 FaceRefine 합성 결과를 연결합니다.

### InsightFace CUDA provider 경고

H3와 YOLO가 사용하는 PyTorch CUDA와 InsightFace의 ONNX Runtime CUDA 버전은 별개입니다. `onnxruntime`과 `onnxruntime-gpu`를 무작정 함께 설치하거나 Torch를 변경하지 마세요. 신원 비교가 CPU로 fallback되어도 H3 생성과 YOLO 검출은 계속 GPU에서 실행될 수 있습니다.

### LUT가 목록에 없음

`.cube` 파일을 `ComfyUI/models/luts/`에 넣고 ComfyUI를 재시작하세요.

## 보안

커스텀 노드는 ComfyUI 프로세스 권한으로 실행됩니다. 설치 전 코드를 검토하고, 타사 노드는 README에 적힌 공식 저장소 주소를 사용하세요. 이 팩은 시작 시 네트워크 다운로드나 pip 설치를 자동으로 실행하지 않습니다.

## 라이선스

Flagship Melona Pack 자체 코드는 [MIT License](LICENSE)로 배포됩니다. 외부 프로젝트와 모델은 각각의 라이선스와 이용 조건을 따릅니다.
