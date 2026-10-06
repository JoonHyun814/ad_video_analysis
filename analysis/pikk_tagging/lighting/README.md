# pikk_tagging/lighting

픽셀 기반 조명 분류 파이프라인. 영상을 step 프레임 간격으로 샘플링해 프레임별 밝기 통계를 추출하고, 규칙 기반 분류기로 조명 유형을 태깅한다.

## 레이블

| 레이블 | 설명 | 핵심 조건 |
|--------|------|-----------|
| `high_key` | 하이키 — 밝고 그림자 적음 | mean_brightness > 155 AND shadow_ratio < 0.12 |
| `low_key` | 로우키 — 어둡고 그림자 많음 | mean_brightness < 82 AND shadow_ratio > 0.38 |
| `backlight` | 역광 — 배경 밝고 피사체 어두움 | bg_center_ratio > 1.45 AND bg_brightness > 115 AND center_brightness < 105 |
| `normal` | 표준 — 나머지 | 위 조건 미충족 |

## 파일 구성

| 파일 | 역할 |
|------|------|
| `analyzer.py` | `analyze_video(path, step)` → frame stats 수집 (OpenCV, 외부 ML 없음) |
| `classifier.py` | `classify_frame(stats)` → label, `temporal_smooth(frames)` → label 부착 + run-length filter |
| `io.py` | `save_results` / `load_results` — lighting_results.json 읽기/쓰기 |
| `cli.py` | CLI 진입점 (`python -m pikk_tagging.lighting.cli`) |
| `viewer.py` | 전체 결과 뷰어 Flask 앱 (포트 5003) |
| `exp_server.py` | 실험 기록 Flask 앱 (포트 8081) — before/after 분류 비교 |
| `docs/experiment_log.html` | 실험 기록 HTML (exp_server 가 서빙) |

## 추출하는 Stats (프레임당)

| 필드 | 설명 |
|------|------|
| `mean_brightness` | 프레임 전체 평균 밝기 (0-255) |
| `brightness_std` | 표준편차 — 대비(contrast) 지표 |
| `shadow_ratio` | 밝기 < 60 픽셀 비율 |
| `highlight_ratio` | 밝기 > 200 픽셀 비율 |
| `center_brightness` | 중앙 영역(25-75% 세로, 20-80% 가로) 평균 |
| `bg_brightness` | 외곽 배경 영역 평균 |
| `bg_center_ratio` | bg_brightness / center_brightness — 역광 지표 |

## CLI

```bash
# 기본 (step=30프레임, min_frames=30)
python -m pikk_tagging.lighting.cli --video path/to/video.mp4

# step 조정 (step=15 → 0.5s 간격 @ 30fps)
python -m pikk_tagging.lighting.cli --video path/to/video.mp4 --step 15

# 출력 디렉토리 지정
python -m pikk_tagging.lighting.cli --video path/to/video.mp4 --out_dir C:/outputs/lighting
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--video` | (필수) | 입력 영상 경로 |
| `--step` | `30` | 분석 간격 (프레임 수) |
| `--min_frames` | `30` | temporal run-length filter 최소 지속 프레임 수 |
| `--out_dir` | `outputs/pikk_output/lighting` | 출력 루트 |

## 출력 구조

```
outputs/pikk_output/lighting/<video_id>/
└── lighting_results.json
```

### lighting_results.json

```json
{
  "video": "C:/path/to/video.mp4",
  "fps": 30.0,
  "step": 30,
  "total_frames": 900,
  "frames": [
    {
      "frame": 0,
      "time": 0.0,
      "label": "high_key",
      "stats": {
        "mean_brightness": 178.4,
        "brightness_std": 38.2,
        "shadow_ratio": 0.031,
        "highlight_ratio": 0.198,
        "center_brightness": 172.1,
        "bg_brightness": 185.3,
        "bg_center_ratio": 1.078
      }
    }
  ]
}
```

## 뷰어

```bash
# 전체 결과 뷰어 (http://localhost:5003)
python -m pikk_tagging.lighting.viewer

# 실험 기록 뷰어 (http://localhost:8081)
python -m pikk_tagging.lighting.exp_server
```
