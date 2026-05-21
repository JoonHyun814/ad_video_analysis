# pipeline 모듈

영상 파일을 읽어 컷 감지 → keyframe 추출 → frames 추출 → OCR까지 수행하는 파이프라인.

## 파일 구성

| 파일 | 역할 |
|------|------|
| `video_loader.py` | DB에서 video_id로 영상 경로 조회 |
| `cuts.py` | 컷 경계 감지 및 컷 병합 유틸리티 |
| `transnetv2_cuts.py` | TransNetV2 딥러닝 기반 컷 경계 감지 |
| `keyframe.py` | 각 컷의 중간 프레임을 JPG로 추출 |
| `frames.py` | 영상 전체에서 지정 fps로 프레임 추출 |
| `ocr.py` | EasyOCR로 이미지에서 텍스트 추출 |
| `cli.py` | 파이프라인 전체를 실행하는 CLI 진입점 |

## 사전 준비

환경 변수 파일이 올바르게 설정되어 있어야 한다.

```
env/db.env   # DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
env/dir.env  # ROOT_VIDEO_DIR
```

## CLI 사용법

`ad_video_analysis/` 디렉토리에서 실행한다.

```bash
python -m pipeline.cli --video_id <ID> [옵션]
```

### 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--video_id` | (필수) | `video_uploads.id` 값 |
| `--cut_backend` | `transnetv2` | 컷 감지 백엔드 (`transnetv2` \| `scenedetect`) |
| `--threshold` | `0.3` (transnetv2) / `27.0` (scenedetect) | 컷 감지 민감도. 낮을수록 더 많은 컷을 감지 |
| `--max_cuts` | 없음 (전체) | 최대 컷 수. 초과 시 짧은 컷을 이웃 중 더 짧은 쪽에 병합 |
| `--out_dir` | `output/<video_id>` | 결과 저장 디렉토리 |

### 예시

```bash
# 기본 실행 (TransNetV2, 전체 컷)
python -m pipeline.cli --video_id 1

# 결과 디렉토리 지정
python -m pipeline.cli --video_id 1 --out_dir tmp/results/1

# 최대 5컷으로 제한 (짧은 컷 병합)
python -m pipeline.cli --video_id 1 --max_cuts 5

# scenedetect 백엔드로 전환
python -m pipeline.cli --video_id 1 --cut_backend scenedetect --threshold 20.0
```

## 파이프라인 단계

```
[1/5] 영상 정보 조회   DB에서 video_id → 영상 절대경로
[2/5] 컷 감지          TransNetV2 (또는 scenedetect) → cuts.json
[3/5] Keyframe 추출    각 컷 중간 프레임 → keyframes/
[4/5] Frames 추출      영상 전체 fps=2 추출 → frames/
[5/5] OCR              frames/ 전체 기준 → ocr.json
```

## 출력 구조

```
{out_dir}/
├── cuts.json          # 컷 목록
├── ocr.json           # OCR 결과
├── keyframes/         # 컷별 중간 프레임 (1장/컷)
│   ├── cut_001_frame_00016.jpg
│   └── ...
└── frames/            # fps=2 전체 프레임
    ├── frame_000000.jpg
    └── ...
```

### cuts.json 예시

```json
[
  {
    "index": 1,
    "start_frame": 0,
    "end_frame": 32,
    "start_sec": 0.0,
    "end_sec": 1.068
  },
  {
    "index": 2,
    "start_frame": 33,
    "end_frame": 64,
    "start_sec": 1.101,
    "end_sec": 2.135
  }
]
```

### ocr.json 예시

```json
{
  "frame_000000.jpg": ["Kurly", "컬리"],
  "frame_000015.jpg": []
}
```

## 컷 감지 백엔드

### TransNetV2 (기본)

딥러닝 기반 장면 전환 감지. 정확도가 높으나 초기 모델 로딩에 수 초 소요.

- `threshold`: 0.0~1.0, 낮을수록 민감 (기본 0.3)
- TensorFlow + ffmpeg 필요

### scenedetect

PySceneDetect ContentDetector. 프레임 간 HSV 히스토그램 차이 기반.

- `threshold`: 낮을수록 민감 (기본 27.0)
- 경량, 빠름

## --max_cuts 병합 알고리즘

`max_cuts` 지정 시 컷 수가 목표에 도달할 때까지 반복 병합한다.

1. 현재 컷 목록에서 가장 짧은 컷(프레임 수 기준)을 찾는다.
2. 앞뒤 이웃 중 더 짧은 쪽에 흡수시킨다 (동률이면 앞쪽).
3. 컷 수가 `max_cuts` 이하가 될 때까지 반복.
