# RAFT — 딥러닝 광학 흐름 카메라 모션 분석 (컷 기반)

RAFT (Recurrent All-Pairs Field Transforms) 딥러닝 모델로 프레임 간 dense optical flow를 계산해 카메라 모션을 분류한다.  
**컷 경계를 먼저 감지**하고 샷 단위로 분석하므로, 씬 전환 프레임이 flow에 섞이지 않는다.

참조: https://github.com/princeton-vl/raft  
구현: `torchvision.models.optical_flow.raft_large / raft_small` (torchvision ≥ 0.13)

## 파일 구성

| 파일 | 역할 |
|------|------|
| `download_video.py` | URL → 로컬 영상 (YouTube: yt-dlp, 직접 링크: urllib) |
| `flow_viz.py` | flow (H,W,2) → RGB 컬러 이미지 (Middlebury 컬러 휠) |
| `raft_flow.py` | 모델 로드 + 컷 감지 + 샷 단위 flow 추론 (`ShotResult` 반환) |
| `motion_classify.py` | flow → `FlowStats` → 모션 분류 (RAFT 전용 임계값 사용) |
| `cli.py` | CLI 진입점 |
| `viewer.py` | Flask 분석 결과 뷰어 (포트 5001) |

## 뷰어 실행

```bash
python -m pikk_tagging.RAFT.viewer          # http://localhost:5001
python -m pikk_tagging.RAFT.viewer --port 5002
```

- **홈**: 분석된 영상 목록 + 모션 분포 배지
- **상세**: 영상 플레이어 + 샷 테이블 (구간별 이동량·flow 시각화 썸네일)
- flow 이미지 클릭 → 전체화면 확대 (ESC 닫기)

## 사전 요구사항

```bash
pip install torchvision   # >= 0.13 (RAFT 포함)
pip install yt-dlp        # YouTube URL 다운로드 시 필요
```

첫 실행 시 torchvision이 pretrained weights (~20 MB)를 자동 다운로드한다.

## CLI 사용법

`ad_video_analysis/` 디렉토리에서 실행한다.

```bash
# YouTube URL에서 다운로드 후 분석
python -m pikk_tagging.RAFT.cli --url https://www.youtube.com/watch?v=VIDEO_ID

# 로컬 영상 분석
python -m pikk_tagging.RAFT.cli --video path/to/video.mp4

# GPU + small 모델 + 빠른 샘플링
python -m pikk_tagging.RAFT.cli --url <URL> --device cuda --model-size small --step 10

# 모델 weights 로컬 경로 지정
python -m pikk_tagging.RAFT.cli --video v.mp4 --model-dir D:\models\RAFT
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--url URL` | (택1 필수) | 영상 URL (YouTube 또는 직접 HTTP/HTTPS 링크) |
| `--video PATH` | (택1 필수) | 로컬 영상 파일 경로 |
| `--out-dir DIR` | `C:\Users\llm\workspace\outputs\pikk_output\RAFT` | 출력 루트 |
| `--step N` | `25` | 샷 내 프레임 샘플링 간격 (25 ≈ 1초@25fps) |
| `--device` | `cpu` | `cpu` \| `cuda` |
| `--model-size` | `large` | `large` (정확) \| `small` (빠름) |
| `--no-resize` | off | 프레임 리사이즈 생략 (고해상도에서 VRAM/RAM 주의) |
| `--model-dir DIR` | 없음 | 모델 weights 저장 경로 (기본: `~/.cache/torch/hub`) |
| `--cookies FILE` | 없음 | Netscape cookies.txt (브라우저 확장으로 내보내기) |
| `--cookies-from-browser BROWSER` | 없음 | `chrome` \| `edge` \| `firefox` (브라우저 닫힌 상태 필수) |
| `--js-runtimes RUNTIME` | 없음 | n-challenge JS 런타임 (예: `deno`) |
| `--remote-components SPEC` | 없음 | EJS 챌린지 솔버 스펙 (예: `ejs:npm`) |

## 분석 흐름

```
영상
  └─ optical_flow.shot_detect.detect_shots()
       └─ [shot_0, shot_1, ..., shot_N]
            └─ 각 샷 내 BGR 컬러 프레임 추출 (step 간격)
                 └─ 연속 프레임 쌍 → RAFT → flow (H,W,2)
                      └─ FlowStats → classify → dominant_motion
```

컷 경계(씬 전환) 프레임 쌍은 완전히 제외된다.

## 출력 구조

```
{out_dir}/<video_id>/
├── <video_id>.mp4           # 다운로드한 영상 (--url 사용 시)
├── flow_viz/
│   ├── shot_00_flow_00000_00025.png
│   └── ...
├── flow_stats.json          # 프레임 쌍별 FlowStats + motion_type
└── motion_summary.json      # 샷별 지배 모션
```

### motion_summary.json 예시

```json
{
  "video": "path/to/video.mp4",
  "fps": 25.0,
  "n_shots": 8,
  "shots": [
    {
      "shot_idx": 0,
      "start_frame": 0, "end_frame": 62,
      "start_sec": 0.0, "end_sec": 2.5,
      "duration_sec": 2.5,
      "dominant_motion": "static",
      "motion_counts": {"static": 2}
    },
    {
      "shot_idx": 1,
      "start_frame": 63, "end_frame": 150,
      "start_sec": 2.52, "end_sec": 6.0,
      "duration_sec": 3.48,
      "dominant_motion": "pan_right",
      "motion_counts": {"pan_right": 3, "static": 1}
    }
  ]
}
```

## 모션 분류 기준

`optical_flow/motion_type.py`의 `classify()` / `aggregate()` 와 동일한 기준을 사용한다.

| 분류 | 조건 |
|------|------|
| `static` | mean_mag < 2.0px (RAFT 노이즈 임계값) |
| `zoom_in` | divergence > 0.01 + zoom이 pan의 1.5배 이상 |
| `zoom_out` | 위와 동일 (음수) |
| `rotate` | rotation_score > 0.015 |
| `pan_*/tilt` | pan_frac > 0.005 (640px 기준 ~1.6px) |
| `handheld` | 방향 일관성 없고 mean_mag > 0.5 |

## classical(Farneback/LK)과의 차이

| 항목 | Farneback / LK | RAFT |
|------|----------------|------|
| 방법 | 고전 CV | 딥러닝 (GRU 반복) |
| 큰 변위 | 취약 (pyramid 제한) | 강함 (all-pairs correlation) |
| 속도 | 빠름 (CPU) | 느림 (GPU 권장) |
| GPU 불필요 | O | X (CPU 가능하나 느림) |
| 의존성 | opencv만 | torchvision + PyTorch |

## 한계

- `--device cpu` 로 긴 영상을 처리하면 매우 느리다. GPU 환경 강력 권장.
- 로우앵글·탑뷰·클로즈업·하이키 등 구도·조명 기법은 flow만으로 감지 불가 (LLM 태거 담당).
- `--no-resize` 없이 640×360 리사이즈하므로 매우 빠른 미세 모션은 누락될 수 있다.
- 컷 감지의 `threshold=28.0` 기본값이 맞지 않으면 샷 경계가 어긋날 수 있다.
