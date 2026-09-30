# pikk_tagging/shot_size

Haar cascade 얼굴 감지 + Canny edge 분석으로 **샷 사이즈(shot size)**를 분류하는 파이프라인.

## 레이블

| 레이블 | 설명 | 핵심 조건 |
|--------|------|-----------|
| `extreme_close_up` | 익스트림 클로즈업 | face_h_ratio > 0.60 |
| `close_up` | 클로즈업 | face_h_ratio > 0.38 (또는 center_edge_ratio > 1.80) |
| `medium_close_up` | 미디엄 클로즈업 | face_h_ratio > 0.22 |
| `medium_shot` | 미디엄 샷 | face_h_ratio > 0.12 (또는 center_edge_ratio > 1.35) |
| `long_shot` | 롱 샷 | face_h_ratio > 0.04 |
| `wide_shot` | 와이드 샷 | 위 조건 미충족 |

얼굴 없는 프레임: `center_edge_ratio` (중앙 edge 밀도 / 전체 edge 밀도) 로 제품·음식 클로즈업 감지.

## 파일 구성

| 파일 | 역할 |
|------|------|
| `analyzer.py` | `analyze_video(path, step)` → Haar cascade 얼굴 감지 + Canny edge stats |
| `classifier.py` | `classify_frame(stats)` → label, `temporal_smooth(frames)` → label 부착 + run-length filter |
| `io.py` | `save_results` / `load_results` — shot_size_results.json 읽기/쓰기 |
| `cli.py` | CLI 진입점 (`python -m pikk_tagging.shot_size.cli`) |
| `viewer.py` | 전체 결과 뷰어 Flask 앱 (포트 5004) |
| `exp_server.py` | 실험 기록 Flask 앱 (포트 8084) — before/after 분류 비교 |
| `docs/experiment_log.html` | 실험 기록 HTML (exp_server 가 서빙) |
| `docs/shot_size_tags.md` | Pikk 샷사이즈 관련 태그 어휘 목록 |

## Stats 필드 (프레임당)

| 필드 | 설명 |
|------|------|
| `face_detected` | 얼굴 감지 여부 (1.0 = 감지, 0.0 = 없음) |
| `face_h_ratio` | 최대 얼굴 높이 / 프레임 높이 (0–1) |
| `face_area_ratio` | 최대 얼굴 면적 / 프레임 면적 (0–1) |
| `face_center_y` | 얼굴 중심 y 위치 비율 (0=상단, 1=하단) |
| `edge_density` | 프레임 전체 edge 픽셀 비율 |
| `center_edge_ratio` | 중앙(20–80%) edge 밀도 / 전체 edge 밀도 |

## CLI

```bash
python -m pikk_tagging.shot_size.cli --video path/to/video.mp4
python -m pikk_tagging.shot_size.cli --video path/to/video.mp4 --step 15
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--video` | (필수) | 입력 영상 경로 |
| `--step` | `30` | 분석 간격 (프레임 수) |
| `--min_frames` | `30` | temporal run-length filter 최소 지속 프레임 수 |
| `--out_dir` | `outputs/pikk_output/shot_size/face_detector` | 출력 루트 |

## 출력 구조

```
outputs/pikk_output/shot_size/face_detector/<video_id>/
└── shot_size_results.json
```

## 뷰어

```bash
python -m pikk_tagging.shot_size.viewer     # http://localhost:5004
python -m pikk_tagging.shot_size.exp_server  # http://localhost:8084
```
