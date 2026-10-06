# pikk_tagging/focus

Laplacian variance 기반으로 **포커스 패턴(얕은 DOF·랙 포커스·딥 포커스)**을 분류하는 파이프라인.

## 레이블

| 레이블 | 설명 | 핵심 조건 |
|--------|------|-----------|
| `out_of_focus` | 전체 아웃 포커스 | global_sharpness < 40 |
| `rack_focus` | 랙 포커스 (초점 이동) | sharpness_delta > 700 |
| `shallow_dof` | 얕은 피사계 심도 (보케) | center_bg_ratio > 2.5 |
| `deep_focus` | 딥 포커스 (전체 선명) | global_sharpness > 250 AND 0.7 ≤ center_bg_ratio ≤ 1.4 |
| `normal` | 표준 | 위 조건 미충족 |

## 파일 구성

| 파일 | 역할 |
|------|------|
| `analyzer.py` | `analyze_video(path, step)` → 프레임별 Laplacian variance (중앙/배경 분리) + 시간축 delta |
| `classifier.py` | `classify_frame(stats)` → label, `temporal_smooth(frames)` → label 부착 + run-length filter |
| `io.py` | `save_results` / `load_results` — focus_results.json 읽기/쓰기 |
| `cli.py` | CLI 진입점 (`python -m pikk_tagging.focus.cli`) |
| `viewer.py` | 전체 결과 뷰어 Flask 앱 (포트 5005) |
| `exp_server.py` | 실험 기록 Flask 앱 (포트 8085) — before/after 분류 비교 |
| `docs/experiment_log.html` | 실험 기록 HTML (exp_server 가 서빙) |
| [`docs/focus_tags.md`](docs/focus_tags.md) | Pikk 포커스 관련 태그 어휘 목록 |

## Stats 필드 (프레임당)

| 필드 | 설명 |
|------|------|
| `global_sharpness` | 프레임 전체 Laplacian variance |
| `center_sharpness` | 중앙 영역(20–80%) Laplacian variance |
| `bg_sharpness` | 외곽 배경 영역 Laplacian variance (4개 스트립 평균) |
| `center_bg_ratio` | center_sharpness / bg_sharpness — shallow DOF 지표 |
| `sharpness_delta` | 이전 프레임과의 global_sharpness 절대 변화량 — rack focus 지표 |

## CLI

```bash
python -m pikk_tagging.focus.cli --video path/to/video.mp4
python -m pikk_tagging.focus.cli --video path/to/video.mp4 --step 15
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--video` | (필수) | 입력 영상 경로 |
| `--step` | `30` | 분석 간격 (프레임 수) |
| `--min_frames` | `30` | temporal run-length filter 최소 지속 프레임 수 |
| `--out_dir` | `outputs/pikk_output/focus/laplacian` | 출력 루트 |

## 출력 구조

```
outputs/pikk_output/focus/laplacian/<video_id>/
└── focus_results.json
```

## 뷰어

```bash
python -m pikk_tagging.focus.viewer     # http://localhost:5005
python -m pikk_tagging.focus.exp_server  # http://localhost:8085
```
