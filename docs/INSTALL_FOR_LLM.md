# Flagship Melona Pack — LLM 설치 지침

## 목표

`ComfyUI-Flagship-Melona-Pack`을 사용자의 ComfyUI 환경을 손상시키지 않고 설치한다. 이 저장소에는 워크플로가 포함되지 않는다.

## 절대 원칙

1. ComfyUI 경로와 실제 사용 Python을 먼저 확인한다. Windows Portable은 보통 `python_embeded/python.exe`다.
2. ZIP의 Python 코드, requirements, pyproject와 타사 저장소의 설치 파일을 실행 전에 검사한다.
3. 기존 `torch`, `torchvision`, `torchaudio`, `triton`, CUDA 패키지, `numpy`, `onnxruntime` 계열을 사용자 승인 없이 변경하지 않는다.
4. 설치 폴더가 이미 있으면 삭제·덮어쓰기 전에 Git 원격, 버전, 로컬 변경을 확인한다.
5. 사용자 이미지, 음원, LUT와 대용량 H3 모델은 임의로 다운로드하거나 대체하지 않는다.

## 1. 이전 분리형 팩 충돌 검사

다음 폴더는 새 통합팩과 동일한 노드 ID를 제공한다.

```text
ComfyUI-H3-Workflow-Tools
ComfyUI-H3-Audio-Cleanup
comfyui_lut_video_exporter
```

하나라도 있으면 새 팩과 동시에 활성화하지 않는다. 삭제 대신 `.disabled` 이름 변경이나 별도 백업 폴더 이동을 먼저 제안하고 사용자 승인을 받는다. 정확한 절대 경로가 ComfyUI의 `custom_nodes` 내부인지 검증한다.

## 2. 통합팩 설치

ZIP의 다음 폴더 하나를 복사한다.

```text
custom_nodes/ComfyUI-Flagship-Melona-Pack
  -> <ComfyUI>/custom_nodes/ComfyUI-Flagship-Melona-Pack
```

통합팩 자체는 pip 패키지를 설치하지 않는다.

## 3. 종속성

현재 ComfyUI Python에서 `torch`, `torchaudio`, `kornia`, `ultralytics`의 import 가능 여부를 먼저 확인한다. 누락된 패키지가 있어도 핵심 패키지 변경이 예상되면 설치를 중단하고 사용자에게 보고한다.

`onnxruntime`과 `onnxruntime-gpu`는 이 팩의 직접 종속성이 아니다. 이를 새로 설치하거나 교체하지 않는다.

## 4. 모델

`face_yolov8m.pt`가 없을 때만 manifest의 공식 주소에서 다음 위치로 내려받는다.

```text
<ComfyUI>/models/ultralytics/bbox/face_yolov8m.pt
```

다른 H3 모델, 이미지, 음원과 LUT는 다운로드하지 않는다.

## 5. 검증

ComfyUI 내장 Python으로 실행한다.

```text
python verify_install.py --comfy-root <ComfyUI 폴더>
```

설치 완료 후 ComfyUI를 완전히 종료하고 다시 실행한다. 이 저장소에는 불러올 예제 워크플로가 없다.
