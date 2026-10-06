# RAFT_step — Dense Step 기반 광학 흐름 카메라 모션 분석

RAFT 딥러닝 모델로 **고정 프레임 간격(step=5)**으로 영상 전체를 밀도 있게 분석한다.  
컷 경계와 무관하게 0.2초마다 샘플링하여 컷 내부의 모션 변화까지 포착한다.  
분석 후 스파이크 제거 + 최소 지속 필터(smooth.py)로 레이블을 정제한다.

참조: [RAFT (arXiv:2003.12039)](https://arxiv.org/abs/2003.12039)  
구현: `torchvision.models.optical_flow.raft_large` (torchvision ≥ 0.13)

## 파일 구성

| 파일 | 역할 |
|------|------|
| `raft_flow.py` | 모델 로드 + step 간격 프레임 쌍 추출 + RAFT flow 추론 (`StepResult` 반환) |
| `motion_classify.py` | flow (H,W,2) → `FlowStats` (raw 수치만, 레이블 없음) |
| `smooth.py` | 스파이크 제거 + 레이블 분류 + temporal filter |
| `cli.py` | CLI 진입점 — `step_results.json` 저장 |
| `viewer.py` | Flask 분석 결과 뷰어 (포트 5002) |
| `flow_viz.py` | flow (H,W,2) → RGB 컬러 이미지 (Middlebury 컬러 휠) |
| `download_video.py` | URL → 로컬 영상 (YouTube: yt-dlp, 직접 링크: urllib) |

## 뷰어 실행

```bash
python -m pikk_tagging.motion.RAFT_step.viewer    # http://localhost:5002
```

- **홈**: 영상 목록 + 레이블 분포 컬러 바 (zoom_in/out·pan·rotate·static 비율)
- **상세**: 영상 플레이어 + 현재 프레임 레이블 배지 + 6개 stats 바 실시간 업데이트
- SPIKE로 감지된 프레임(컷 경계 보간)은 "SPIKE (보간값)" 태그 별도 표시
- flow viz 썸네일 클릭 → 라이트박스 확대

## 사전 요구사항

```bash
pip install torchvision   # >= 0.13
pip install flask
pip install yt-dlp        # YouTube URL 다운로드 시 필요
```

## CLI 사용법

`ad_video_analysis/` 디렉토리에서 실행한다.

```bash
# 로컬 영상 분석 (step=5 기본값)
python -m pikk_tagging.motion.RAFT_step.cli --video path/to/video.mp4

# YouTube URL
python -m pikk_tagging.motion.RAFT_step.cli --url https://www.youtube.com/watch?v=VIDEO_ID

# step 변경
python -m pikk_tagging.motion.RAFT_step.cli --video v.mp4 --step 5 --device cpu
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--url URL` | (택1 필수) | 영상 URL |
| `--video PATH` | (택1 필수) | 로컬 영상 파일 경로 |
| `--out-dir DIR` | `…/pikk_output/RAFT_step_s5` | 출력 루트 |
| `--step N` | `5` | 프레임 샘플링 간격 (5 = 0.2s @ 25fps) |
| `--device` | `cpu` | `cpu` \| `cuda` |
| `--model-size` | `large` | `large` \| `small` |
| `--no-resize` | off | 640×360 리사이즈 생략 |
| `--model-dir DIR` | 없음 | weights 저장 경로 |

## smooth.py — 후처리 파이프라인

`cli.py`가 저장한 raw `step_results.json`에 후처리를 적용하여 레이블을 반환한다.  
뷰어 API와 별도 스크립트 모두에서 사용한다.

```python
from pikk_tagging.motion.RAFT_step.smooth import smooth_and_classify

rows = smooth_and_classify(pairs, step=5, min_frames=10, acc_window=9)
# rows[i]: {frame_a, frame_b, time_a, time_b, label, is_spike, stats, flow_viz}
```

### 처리 단계

```
raw pairs (step_results.json)
    │
    ▼
1. detect_spikes()
   mean_mag이 로컬 윈도우(±5스텝) 중앙값의 3배 이상 → SPIKE 마킹
    │
    ▼
2. _interp_stats()
   SPIKE 위치 stats를 좌우 비스파이크 이웃으로 선형 보간
    │
    ▼
3. classify_stats() + _rolling_sum_stats() fallback
   우선순위: zoom > pan > rotation
   - |zoom_score| > 0.05  → zoom_in / zoom_out
   - |pan_x| > 5px or |pan_y| > 5px  → pan_right/left, tilt_up/down
   - |rotation_score| > 0.015  → rotate_cw / rotate_ccw
   - mean_mag < 3px  → static
   - 나머지  → motion
   ※ static/motion일 때 acc_window(기본 9) 구간 합산 stats로 재분류
     — zoom_in/zoom_out만 승격 허용 (느린 줌 감지용)
     — pan/rotation은 배경 피사체 노이즈가 누적 합산에서 임계값을 넘는
       오탐이 발생하므로 rolling sum 승격에서 제외
    │
    ▼
4. temporal_filter()
   min_frames(기본 10) 미만 지속 레이블을 이웃 레이블로 교체 (수렴까지 반복)
    │
    ▼
레이블 부여된 rows
```

### 레이블 목록

| 레이블 | 의미 |
|--------|------|
| `zoom_in` | 화면 바깥 방향 발산 (divergence > 0) |
| `zoom_out` | 화면 안쪽 수렴 (divergence < 0) |
| `pan_right` / `pan_left` | 수평 카메라 이동 |
| `tilt_up` / `tilt_down` | 수직 카메라 이동 |
| `rotate_cw` / `rotate_ccw` | 카메라 롤 회전 |
| `motion` | 움직임 있으나 지배 성분 없음 (피사체 로컬 모션 가능) |
| `static` | mean_mag < 3px |

### 파라미터

| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `_MIN_MAG` | 3.0 px | static 경계 |
| `_ZOOM_THRESH` | 0.05 | zoom 분류 임계값 |
| `_PAN_THRESH` | 5.0 px | pan 분류 임계값 |
| `_ROT_THRESH` | 0.015 | rotation 분류 임계값 |
| `_SPIKE_FACTOR` | 3.0× | 스파이크 감지 배율 |
| `_SPIKE_MIN_MAG` | 15.0 px | 스파이크 최소 크기 |
| `min_frames` | 10 | 레이블 최소 지속 프레임 수 |
| `acc_window` | 9 | 누적 fallback 윈도우 크기 — zoom_in/zoom_out 승격 전용 (pan/rotation은 노이즈 오탐 방지를 위해 제외) |

## 출력 구조

```
{out_dir}/<video_id>/
├── step_results.json       # raw stats (label 없음)
└── flow_viz/
    ├── flow_00000_00005.png
    └── ...
```

### step_results.json 예시

```json
{
  "video": "path/to/video.mp4",
  "fps": 25.0,
  "step": 5,
  "total_frames": 679,
  "total_pairs": 135,
  "pairs": [
    {
      "frame_a": 0,
      "frame_b": 5,
      "time_a": 0.0,
      "time_b": 0.2,
      "flow_viz": "flow_00000_00005.png",
      "stats": {
        "zoom_score": 0.0152,
        "pan_x": 2.45,
        "pan_y": 0.56,
        "rotation_score": -0.0039,
        "flow_var": 1.63,
        "mean_mag": 2.75
      }
    }
  ]
}
```

레이블(`label`, `is_spike`)은 JSON에 저장하지 않으며, 뷰어/스크립트에서 `smooth_and_classify()`를 호출해 실시간으로 계산한다.

## RAFT vs RAFT_step 비교

| 항목 | RAFT (컷 기반) | RAFT_step (step=5) |
|------|--------------|------------------|
| 분석 단위 | 컷(shot) 1개당 1쌍 | 5프레임마다 1쌍 |
| 컷 내부 변화 | 감지 불가 | 감지 가능 |
| 최소 감지 이벤트 | 컷 길이 의존 | **0.2s (5프레임)** |
| 스파이크 처리 | 컷 경계 = 스파이크 없음 | smooth.py로 보간 |
| 출력 | 컷별 단일 레이블 | 프레임 구간별 raw stats + 후처리 레이블 |
| 연산량 | 낮음 | 높음 (2× step=10) |

## 한계

- CPU에서 긴 영상(> 3분)은 처리 시간이 오래 걸린다. GPU 권장.
- `motion` 레이블은 피사체 로컬 모션과 약한 카메라 글로벌 모션을 구분하지 않는다.  
  `flow_var` 값을 기준으로 세분화 가능 (향후 개선 예정).
- smooth.py 임계값은 25fps 광고 영상 기준 수동 튜닝값이며, fps가 다르면 재보정 필요.
