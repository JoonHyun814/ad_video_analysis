# pikk_tagging/LLM

Qwen2.5-VL 로컬 모델로 영상을 fps=2 속도로 프레임별 분석해 도메인별 대표 태그를 추출하는 파이프라인.

> **motion 도메인은 제외** — 다중 프레임 컨텍스트가 필요하므로 VL 단일 프레임 추론에 적합하지 않다.

## 지원 도메인 및 레이블

| 도메인 | 레이블 |
|--------|--------|
| `angle` | 탑뷰, 드론샷, 로우앵글, 아이레벨, 하이앵글, 더치앵글 |
| `shot_size` | 익스트림클로즈업, 클로즈업, 미디엄클로즈업, 미디엄샷, 롱샷, 와이드샷, 풀샷 |
| `lighting` | 역광, 실루엣, 로우키, 하이키, 흑백, 레트로, 일반조명 |
| `focus` | 아웃포커스, 딥포커스, 랙포커스, 소프트포커스, 팬포커스 |

## 파일 구성

| 파일 | 역할 |
|------|------|
| `model.py` | Qwen2.5-VL 로더 및 단일 프레임 추론 (`QwenVLModel`, `InferenceResult`) |
| `prompts.py` | 도메인별 분류 프롬프트 생성 (`build_prompt`, `DOMAIN_LABELS`) |
| `analyzer.py` | fps 기반 프레임 추출 + VL 추론 루프 (`analyze_video`) |
| `aggregator.py` | 프레임별 태그 → 도메인별 최빈 태그 집계 (`compute_dominant_tags`) |
| `io.py` | 결과 JSON 저장/로딩 (`save_results`, `load_results`) |
| `cli.py` | CLI 진입점 |
| `viewer.py` | 결과 뷰어 Flask 앱 (포트 5007) |

## CLI

```bash
# 기본 (모든 도메인 분석)
python -m pikk_tagging.LLM.cli --video path/to/video.mp4

# 특정 도메인만
python -m pikk_tagging.LLM.cli --video path/to/video.mp4 --target_domain angle,focus

# 커스텀 모델 경로 / 출력 경로
python -m pikk_tagging.LLM.cli \
  --video path/to/video.mp4 \
  --target_domain angle,focus,shot_size,lighting \
  --model_path D:\models\Qwen2.5-VL-7B-Instruct \
  --out_dir outputs/pikk_output/LLM/qwen_vl \
  --fps 2.0
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--video` | (필수) | 입력 영상 경로 |
| `--target_domain` | 전체 도메인 | 콤마 구분 도메인 (`angle,focus,shot_size,lighting`) |
| `--fps` | `2.0` | 초당 분석 프레임 수 |
| `--model_path` | `D:\models\Qwen2.5-VL-7B-Instruct` | Qwen VL 모델 디렉토리 |
| `--out_dir` | `outputs/pikk_output/LLM/qwen_vl` | 결과 저장 루트 |

## 출력 구조

```
outputs/pikk_output/LLM/qwen_vl/
├── video_gt_tags.json            # (선택) GT 태그 파일
└── <video_id>/
    └── vl_results.json
```

`vl_results.json` 주요 필드:

```json
{
  "video": "path/to/video.mp4",
  "model": "Qwen2.5-VL-7B-Instruct",
  "model_path": "D:/models/Qwen2.5-VL-7B-Instruct",
  "fps": 2.0,
  "target_domains": ["angle", "focus", "shot_size", "lighting"],
  "total_frames": 120,
  "inference_time_sec": 45.2,
  "tokens_used": {"input": 10000, "output": 2500, "total": 12500},
  "resource_usage": {
    "gpu_memory_peak_mb": 8192.0,
    "cpu_percent_avg": 15.2,
    "gpu_util_avg": 85.3
  },
  "dominant_tags": {
    "angle": "로우앵글",
    "focus": "아웃포커스",
    "shot_size": "클로즈업",
    "lighting": "하이키"
  },
  "frames": [
    {"frame_idx": 0, "time": 0.0, "tags": {"angle": "로우앵글", ...}}
  ]
}
```

## 뷰어

```bash
python -m pikk_tagging.LLM.viewer  # http://localhost:5007
```

뷰어 화면 구성:
- **홈**: 영상별 도메인 대표 태그 + GT 태그 목록
- **상세**: 비디오 플레이어 + GT 태그 + 대표 태그 + 현재 프레임 태그(재생 연동) + 타임라인(도메인별 색상)

## GT 태그 파일 형식 (`video_gt_tags.json`)

```json
{
  "<video_id>": {
    "all_tags": ["탑뷰", "역광", "아웃포커스"],
    "angle_tags": ["탑뷰"],
    "lighting_tags": ["역광"],
    "focus_tags": ["아웃포커스"],
    "shot_size_tags": []
  }
}
```

## 환경

```
가상환경: C:\Users\llm\workspace\.venv-train
모델 저장 경로: D:\models\<model-name>
```

모델 로드 전 필수 패키지:
```bash
pip install transformers torch accelerate qwen-vl-utils pillow opencv-python psutil
```
