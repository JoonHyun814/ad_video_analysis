# optical_flow — Farneback / Lucas-Kanade 카메라 모션 감지

Dense(Farneback) + Sparse(Lucas-Kanade) Optical Flow 두 방식으로 카메라 모션 유형을 분류한다.
SQL `visual_elements` 레이블과의 비교 테스트: **3/4 (75%)** — OSH 호모그라피 방법(0/4) 대비 개선.

## 파일 구성

| 파일 | 역할 |
|------|------|
| `flow_utils.py` | 프레임 추출(`extract_window`, `extract_full`), 영상 메타, 로그 |
| `motion_type.py` | `FlowStats` / `MotionResult` 데이터클래스, `classify()`, `aggregate()`, `dense_flow_stats()`, `sparse_flow_stats()` |
| `farneback.py` | `cv2.calcOpticalFlowFarneback` 기반 dense flow 분석 |
| `lucas_kanade.py` | GFTT + `cv2.calcOpticalFlowPyrLK` 기반 sparse flow 추적, 4-DOF 회귀로 zoom/pan 분리 |
| `cli.py` | CLI 진입점 (`video` / `compare` subcommand) |

## CLI 사용법

```bash
# 영상 전체 모션 분석 (Farneback + LK 동시)
python -m pikk_tagging.optical_flow.cli video path/to/video.mp4 --step 25

# SQL 레이블 vs CV 감지 비교 (4개 테스트 케이스 고정)
python -m pikk_tagging.optical_flow.cli compare --window 5 --step-sec 1.0
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--step N` | `25` | video 모드: N 프레임마다 샘플링 (25 ≈ 1초@25fps) |
| `--window SEC` | `5.0` | compare 모드: 타임스탬프 ±창 크기(초) |
| `--step-sec SEC` | `1.0` | compare 모드: 프레임 쌍 간격(초) — 클수록 느린 줌 감지 용이 |

## 모션 분류 기준

| 분류 | 조건 |
|------|------|
| `zoom_in` | `zoom_score > 0.01` + `zoom > pan_frac × 1.5` (양수) |
| `zoom_out` | 위와 동일 (음수) |
| `rotate` | `rotation_score > 0.015` |
| `pan_*` | `pan_frac > 0.005` (≈1.6px / 640px 프레임) |
| `static` | 모든 성분 임계값 미만 |
| `cut` | 유효 포인트 수 < 10 |

`zoom_score`(분수)와 `pan`(픽셀)을 같은 단위로 비교하기 위해 pan은 프레임 반너비(320px)로 정규화.

## 알고리즘 차이

| 항목 | Farneback (dense) | Lucas-Kanade (sparse) |
|------|------------------|----------------------|
| 입력 | 전체 픽셀 flow 필드 | GFTT 코너 300개 |
| zoom 추정 | divergence (∂u/∂x + ∂v/∂y) | 4-DOF LSQ 회귀 (tx, ty, ds, θ) |
| 장점 | 안정적, 씬컷에 강함 | pan/zoom 독립 분리 |
| 단점 | 느린 줌 임계값 민감 | 씬컷 시 회귀 오류 가능 |

## 감지 가능 / 불가 기법 (SQL 데이터 기준)

| 기법 | SQL 건수 | 감지 가능? |
|------|----------|-----------|
| 줌인 / 줌아웃 | ~45 | **✓ 가능** (본 모듈) |
| 팬 / 틸트 | ~20 | **✓ 가능** (씬컷 없을 때) |
| 핸드헬드 | ~19 | **✓ 가능** (flow variance 높음) |
| 트래킹샷 | ~821 | **△ 부분** (피사체 추적 vs 카메라 구분 어려움) |
| 로우앵글 / 탑뷰 | ~1,380 | **✗ 불가** — 소실점·수평선 분석 필요 |
| 클로즈업 / 샷크기 | ~5,000 | **✗ 불가** — 얼굴/몸 감지 필요 |
| 아웃포커스 | ~3,300 | **✗ 불가** — Laplacian 분산 분석 필요 |
| 하이키 / 역광 등 | ~3,000 | **✗ 불가** — 밝기 히스토그램 분석 필요 |
