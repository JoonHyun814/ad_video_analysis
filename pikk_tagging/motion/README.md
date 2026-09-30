# pikk_tagging/motion

카메라 모션(pan·tilt·zoom·rotate·static)을 광학 흐름 기반으로 감지하는 파이프라인 모음.  
4가지 방법론이 각각의 서브폴더에 구현되어 있으며 상황에 맞는 방법을 선택해 사용한다.

## 방법론 비교

| 서브폴더 | 방법 | 특징 | 권장 용도 |
|---------|------|------|-----------|
| [`optical_flow/`](optical_flow/README.md) | Farneback (dense) + Lucas-Kanade (sparse) | 외부 모델 없음, 빠름 | zoom·pan·rotate 감지 (SQL 레이블 3/4 일치) |
| [`OSH/`](OSH/README.md) | ORB/SIFT + RANSAC + Homography | 특징점 기반 | 컷 감지·유사도 측정 |
| [`RAFT/`](RAFT/README.md) | RAFT 딥러닝 dense flow | 높은 정확도, GPU 권장 | 정밀 모션 추정 |
| [`RAFT_step/`](RAFT_step/README.md) | RAFT + step=5 smooth | 컷 내부 모션 변화 감지 | 0.2s 해상도 세밀 분석 |

## 감지 레이블

`optical_flow` 와 `RAFT_step` 이 공통으로 사용하는 레이블:

| 레이블 | 설명 | 감지 원리 |
|--------|------|-----------|
| `static` | 카메라 정지 | 전체 평균 이동량 ≈ 0 |
| `pan` | 수평/수직 평행 이동 | `mean(u)` 또는 `mean(v)` 편향 |
| `zoom_in` | 줌 인 | divergence 양수 (벡터 발산) |
| `zoom_out` | 줌 아웃 | divergence 음수 (벡터 수렴) |
| `rotate` | 카메라 회전 (roll) | curl 성분 주도 |

## CLI 사용법

```bash
# optical_flow — zoom·pan·rotate 감지
python -m pikk_tagging.motion.optical_flow.cli video path/to/video.mp4 --step 25
python -m pikk_tagging.motion.optical_flow.cli compare --window 5 --step-sec 1.0

# OSH — 영상 유사도·컷 감지
python -m pikk_tagging.motion.OSH.feature_match video path/to/video.mp4 --detector orb --step 30
python -m pikk_tagging.motion.OSH.feature_match similarity a.mp4 b.mp4

# RAFT — 딥러닝 dense flow
python -m pikk_tagging.motion.RAFT.cli --video path/to/video.mp4 --device cuda

# RAFT_step — 세밀 분석 + 뷰어
python -m pikk_tagging.motion.RAFT_step.cli --video path/to/video.mp4 --step 5
python -m pikk_tagging.motion.RAFT_step.viewer   # http://localhost:5002
```

## 출력 구조

```
outputs/pikk_output/motion/<방법론>/<video_id>/
└── motion_results.json
```

## 관련 문서

- [`docs/motion_tags.md`](docs/motion_tags.md) — Pikk 카메라 모션 태그 어휘 목록 및 분류기 매핑
- [`docs/camera_motion_detection.md`](docs/camera_motion_detection.md) — 광학 흐름 이론 및 RAFT 아키텍처 설명
- [`docs/experiment_log.html`](docs/experiment_log.html) — 방법론 비교 실험 기록
