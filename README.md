# Flagship Melona Pack

MiniMax H3 장편 영상 워크플로에서 실제로 발생한 문제를 해결하기 위해 만든 ComfyUI 커스텀 노드팩입니다.

이 팩은 얼굴이 없는 장면에서 불필요한 FaceRefine 실행을 자동으로 건너뛰고, 긴 영상의 최종 색상 보정이 VRAM을 모두 사용하는 문제를 방지합니다. 또한 H3 생성 음성의 저역 공명음을 동적으로 줄이고 `.cube` LUT를 영상 프레임에 적용하는 기능을 제공합니다.

> 이 저장소에는 커스텀 노드 코드와 설치 문서만 들어 있습니다. 워크플로, H3 모델, 개인 이미지·음원·LUT, 타사 커스텀 노드는 포함하지 않습니다.

## 포함된 노드

### `[Melona] H3 Face Presence — Auto Bypass`

현재 영상 배치 전체를 얼굴 검출기로 확인하고 `face_found` Boolean 값을 출력합니다.

- 얼굴 발견: Lazy Switch가 FaceRefine 경로를 실행
- 얼굴 없음: FaceRefine 샘플러 전체를 건너뛰고 원본 프레임을 그대로 전달
- 장점: 얼굴 없는 장면에서 오류가 발생하지 않고 두 번째 H3 샘플링 시간도 절약
- 필요 모델: `face_yolov8m.pt`

얼굴 검사는 약간의 시간이 추가되지만, 얼굴이 없는 장면에서 훨씬 무거운 H3 얼굴 재생성을 실행하지 않는 것이 목적입니다.

### `[Melona] Color Match LAB — VRAM Safe`

긴 영상의 전체 `IMAGE` 배치를 GPU에 한 번에 올리지 않고 작은 프레임 묶음으로 나누어 LAB 색상을 맞춥니다.

- Reinhard LAB 방식
- `strength`: 색상 보정 강도
- `chunk_size`: GPU에서 동시에 처리할 프레임 수
- `free_vram_first`: 완료된 모델을 내린 후 색상 보정 시작
- 권장값: `strength=0.30`, `chunk_size=2`, `free_vram_first=true`

기존 GPU 색상 보정은 1088×1920 장편 영상 수백 프레임을 한 번에 VRAM으로 이동하면서 30GB 이상을 요구할 수 있습니다. 이 노드는 전체 배치를 시스템 메모리에 두고 1~2프레임씩 처리합니다.

### `[Melona] H3 Dynamic Resonance Suppressor`

H3 생성 오디오에서 특정 저·중역대가 과도하게 울릴 때만 해당 대역을 줄이는 동적 공명 억제기입니다.

- AI 모델이나 노멀라이저가 아님
- 전체 음량을 무조건 낮추지 않음
- 중심 주파수, Q, 임계값, 비율, 최대 감소량, Attack/Release 조절 가능
- 대화·노래에서 발생하는 통 울림을 미세하게 줄이는 용도

기본 시작점은 `center=320Hz`, `Q=0.8`, `threshold=-22dB`, `ratio=2.5`, `max reduction=2dB`입니다.

### `[Melona] Apply LUT to Video Frames`

Premiere Pro와 CapCut 등에서 사용하는 `.cube` LUT를 ComfyUI `IMAGE` 프레임 배치에 적용합니다.

- LUT를 최종 인코딩 전에 적용 가능
- 프레임 묶음 단위 처리
- `lut_strength`로 원본과 혼합
- LUT 파일 위치: `ComfyUI/models/luts/`

영상 전체의 색감을 통일하려면 장면별 생성 단계가 아니라 최종 조립·인코딩 직전에 연결하는 것을 권장합니다.

### `[Melona] LUT Video Save`

LUT 적용과 FFmpeg 영상 저장을 한 번에 수행하는 선택형 출력 노드입니다.

- H.264 고화질
- H.264 RGB 무손실
- ProRes 4444
- FFV1 무손실
- 선택적 오디오 결합

프레임과 오디오를 한 번에 파일로 저장하고 싶을 때 사용하는 독립형 출력 노드입니다.

## 설치

### Git으로 설치

ComfyUI의 `custom_nodes` 폴더에서 실행합니다.

```bash
git clone https://github.com/ych8836-ops/flagship-melona-pack.git ComfyUI-Flagship-Melona-Pack
```

ComfyUI를 완전히 종료한 뒤 다시 실행합니다. 정상적으로 설치되면 노드 검색에서 `[Melona]`를 검색할 수 있습니다.

### ZIP으로 설치

1. GitHub의 `Code → Download ZIP`을 선택합니다.
2. 압축을 풉니다.
3. 폴더 이름을 `ComfyUI-Flagship-Melona-Pack`으로 변경합니다.
4. 폴더를 `ComfyUI/custom_nodes/` 아래에 넣습니다.
5. ComfyUI를 완전히 재시작합니다.

최종 구조:

```text
ComfyUI/
└─ custom_nodes/
   └─ ComfyUI-Flagship-Melona-Pack/
      ├─ __init__.py
      ├─ workflow_nodes.py
      ├─ audio_nodes.py
      ├─ lut_nodes.py
      └─ lut_cube.py
```

### LLM 에이전트로 설치

파일과 터미널을 다룰 수 있는 LLM에게 [`docs/COPY_THIS_TO_LLM.txt`](docs/COPY_THIS_TO_LLM.txt)의 내용을 전달하세요. 자세한 안전 절차는 [`docs/INSTALL_FOR_LLM.md`](docs/INSTALL_FOR_LLM.md)에 있습니다.

LLM 지침은 다음을 요구합니다.

- 실제 ComfyUI Python 확인
- 설치 전 코드와 종속성 검사
- 기존 Torch·CUDA·ONNX Runtime 보호
- 이전 분리형 노드팩 충돌 검사
- 누락된 실행 패키지만 확인하고 기존 Torch·CUDA 환경은 변경하지 않기
- 설치 후 다섯 노드와 얼굴 검출 모델 검증

## 이전 분리형 팩에서 이전

이 통합팩은 다음의 이전 로컬 폴더와 동일한 노드 ID를 제공합니다.

```text
ComfyUI-H3-Workflow-Tools
ComfyUI-H3-Audio-Cleanup
comfyui_lut_video_exporter
```

새 통합팩과 동시에 활성화하면 중복 노드 등록이 발생할 수 있습니다. 기존 폴더를 백업하거나 폴더 이름 끝에 `.disabled`를 붙인 뒤 통합팩을 설치하세요. 삭제 전에는 반드시 정확한 경로를 확인하세요.

## 노드팩 자체 요구사항

이 저장소는 ComfyUI의 기존 Torch·CUDA 환경을 보호하기 위해 시작 시 pip 설치를 실행하지 않으며 `requirements.txt`도 핵심 패키지를 강제로 변경하지 않습니다. 아래 모듈이 없는 경우 ComfyUI가 실제로 사용하는 Python에서 누락된 것만 설치하세요.

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

검증기는 다섯 Melona 노드, 이전 분리형 폴더 충돌과 얼굴 검출 모델을 확인합니다. FaceRefine 같은 선택형 외부 노드는 검사 대상이 아닙니다.

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

