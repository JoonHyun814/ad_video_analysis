# pikk_tagging/angle

Hough 직선 변환으로 수평선 위치·roll 각도를 추정해 **카메라 앵글**을 분류하는 파이프라인.

## 레이블

| 레이블 | 설명 | 핵심 조건 |
|--------|------|-----------|
| `dutch_angle` | 더치 앵글 | \|roll_angle_deg\| > 15° |
| `bird_eye` | 버드 아이 / 탑뷰 | h_line_ratio > 0.65 AND v_line_ratio < 0.10 |
| `high_angle` | 하이 앵글 | horizon_y_ratio < 0.35 (수평선 상단) |
| `eye_level` | 아이 레벨 | horizon 0.35 ~ 0.65 |
| `low_angle` | 로우 앵글 | horizon_y_ratio > 0.65 (수평선 하단) |

## 파일 구성

| 파일 | 역할 |
|------|------|
| `analyzer.py` | `analyze_video(path, step)` → Hough 직선 분석 + horizon y 추정 |
| `classifier.py` | `classify_frame(stats)` → label, `temporal_smooth(frames)` → label 부착 + run-length filter |
| `io.py` | `save_results` / `load_results` — angle_results.json 읽기/쓰기 |
| `cli.py` | CLI 진입점 (`python -m pikk_tagging.angle.cli`) |
| `viewer.py` | 전체 결과 뷰어 Flask 앱 (포트 5006) |
| `exp_server.py` | 실험 기록 Flask 앱 (포트 8086) — before/after 분류 비교 |
| `docs/experiment_log.html` | 실험 기록 HTML (exp_server 가 서빙) |
| [`docs/angle_tags.md`](docs/angle_tags.md) | Pikk 앵글 관련 태그 어휘 목록 |

## Stats 필드 (프레임당)

| 필드 | 설명 |
|------|------|
| `roll_angle_deg` | 수평선 기울기 (수평 기준 편차, 단위: °) |
| `horizon_y_ratio` | 추정 수평선 y 위치 비율 (0=상단, 1=하단) |
| `h_line_ratio` | 수평선(theta 60°~120°) 비율 |
| `v_line_ratio` | 수직선(theta 0°~20° 또는 160°~180°) 비율 |
| `line_count` | 감지된 Hough 직선 총 개수 |

## CLI

```bash
python -m pikk_tagging.angle.cli --video path/to/video.mp4
python -m pikk_tagging.angle.cli --video path/to/video.mp4 --step 15
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--video` | (필수) | 입력 영상 경로 |
| `--step` | `30` | 분석 간격 (프레임 수) |
| `--min_frames` | `30` | temporal run-length filter 최소 지속 프레임 수 |
| `--out_dir` | `outputs/pikk_output/angle/hough_lines` | 출력 루트 |

## 출력 구조

```
outputs/pikk_output/angle/hough_lines/<video_id>/
└── angle_results.json
```

## 뷰어

```bash
python -m pikk_tagging.angle.viewer     # http://localhost:5006
python -m pikk_tagging.angle.exp_server  # http://localhost:8086
```
