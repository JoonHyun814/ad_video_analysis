# pipeline 모듈

영상 파일을 읽어 컷 감지 → keyframe 추출 → OCR까지 수행하는 파이프라인.

## 파일 구성

| 파일 | 역할 |
|------|------|
| `video_loader.py` | DB에서 video_id로 영상 경로 조회 |
| `cuts.py` | ContentDetector(PySceneDetect)로 컷 경계 감지 |
| `keyframe.py` | 각 컷의 중간 프레임을 JPG로 추출 |
| `ocr.py` | EasyOCR로 keyframe 이미지에서 텍스트 추출 |
| `cli.py` | 파이프라인 전체를 실행하는 CLI 진입점 |

## 사전 준비

```powershell
. .venv\Scripts\Activate.ps1
```

## CLI 사용법

```powershell
python -m pipeline.cli --video_id <ID>
```

### 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--video_id` | (필수) | `video_uploads.id` 값 |
| `--threshold` | `27.0` | 컷 감지 민감도. 낮을수록 더 많은 컷을 감지 |

### 예시

```powershell
# 기본 실행
python -m pipeline.cli --video_id 1

# 컷 감지를 더 민감하게
python -m pipeline.cli --video_id 1 --threshold 20.0
```

## 출력 구조

```
output/
└── {video_id}/
    ├── cuts.json          # 컷 목록 (index, start_frame, end_frame, start_sec, end_sec)
    ├── ocr.json           # OCR 결과 {파일명: [텍스트, ...]}
    └── keyframes/
        ├── cut_001_frame_00123.jpg
        ├── cut_002_frame_00456.jpg
        └── ...
```

### cuts.json 예시

```json
[
  {
    "index": 1,
    "start_frame": 0,
    "end_frame": 71,
    "start_sec": 0.0,
    "end_sec": 2.984
  },
  ...
]
```

### ocr.json 예시

```json
{
  "cut_001_frame_00035.jpg": ["Samsung", "갤럭시 S25"],
  "cut_002_frame_00120.jpg": []
}
```

## 컷 감지 알고리즘

`transnetv2` PyPI 패키지는 Python 3.14를 지원하지 않아 (TensorFlow 의존성),  
동일한 역할을 하는 **PySceneDetect ContentDetector**를 사용한다.

- ContentDetector: 프레임 간 HSV 히스토그램 차이를 기반으로 컷 경계 감지
- threshold를 낮추면 더 세밀하게, 높이면 큰 변화만 감지
