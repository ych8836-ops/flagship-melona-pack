# 수동 설치 상세 안내

## 1. ComfyUI 위치 확인

다음 폴더가 있는 위치를 찾습니다.

```text
ComfyUI/custom_nodes
ComfyUI/models
```

Windows Portable은 보통 실행 폴더에 `python_embeded`와 `ComfyUI`가 함께 있습니다.

## 2. 중복 폴더 확인

다음 이전 분리형 폴더가 있으면 새 통합팩과 동시에 사용하지 않습니다.

```text
ComfyUI-H3-Workflow-Tools
ComfyUI-H3-Audio-Cleanup
comfyui_lut_video_exporter
```

복구 가능하게 폴더를 백업한 뒤 비활성화하세요.

## 3. Flagship Melona Pack 설치

이 저장소 전체가 다음 위치에 오도록 설치합니다.

```text
ComfyUI/custom_nodes/ComfyUI-Flagship-Melona-Pack
```

중첩 폴더가 생기지 않도록 주의합니다.

잘못된 예:

```text
custom_nodes/ComfyUI-Flagship-Melona-Pack/flagship-melona-pack-main/__init__.py
```

올바른 예:

```text
custom_nodes/ComfyUI-Flagship-Melona-Pack/__init__.py
```

## 4. 얼굴 검출 모델

`H3 Face Presence` 노드를 사용하려면 `face_yolov8m.pt`를 다음 위치에 둡니다.

```text
ComfyUI/models/ultralytics/bbox/face_yolov8m.pt
```

## 5. 재시작과 확인

ComfyUI를 완전히 종료하고 재실행합니다. 노드 검색에서 `[Melona]`를 검색해 다섯 노드가 표시되는지 확인합니다.

이 저장소에는 예제 워크플로가 포함되지 않습니다. 자신의 워크플로에 필요한 Melona 노드만 추가해 연결하세요.
