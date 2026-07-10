# train_pipeline 모듈

`pipeline` 분석 결과를 Qwen VL 학습용 JSONL 데이터셋으로 빌드하고, YAML 설정으로 학습을 실행한다.

## 파일 구성

| 파일 | 역할 |
|------|------|
| `cli.py` | 데이터셋 빌드 / 학습 진입점 |
| `dataset_builder.py` | scene·cut·scenario 3종 JSONL 빌드 + 이미지 사본 |
| `holdout.py` | video_id 기준 학습/홀드아웃 분리 + 매니페스트 저장 |
| `schema_check.py` | 컷 수 일치·필드 완전성 등 구조 검사 (parse_failed 이외의 결함 탐지) |
| `compare_outputs.py` | 홀드아웃 video_id 로 before/after 산출물의 구조 품질 비교 |
| `trainer.py` | YAML 설정 로드 + 학습 루프 |
| `configs/` | 학습 설정 YAML 샘플 |
| `Dockerfile` | 학습 전용 이미지 (Claude Code + unsloth LoRA 학습 스택) |

## 사용법

```bash
# 1) 데이터셋 빌드 (홀드아웃 15% 분리 — 학습 후 before/after 비교용으로 남겨둠)
python -m train_pipeline.cli --build_dataset --data_dir output/ [output2/ ...] --out_dir data/ \
    --holdout_ratio 0.15 --holdout_seed 42

# 2) 학습
python -m train_pipeline.cli --config configs/sample --out_dir runs/exp1
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--build_dataset` | — | 데이터셋 빌드 모드 (`--config` 와 상호 배타) |
| `--config` | — | 학습 모드. YAML 경로 (`.yaml` 자동 보강) |
| `--data_dir` | `output/` | 분석 결과 루트 (여러 경로 가능) |
| `--out_dir` | (필수) | 빌드/학습 결과 저장 디렉토리 |
| `--holdout_ratio` | `0.0` | 0보다 크면 video_id 기준으로 이 비율만큼 학습에서 제외하고 매니페스트 저장 |
| `--holdout_seed` | `42` | 홀드아웃 샘플링 시드 (재현성) |
| `--holdout_out` | `<out_dir>/holdout_video_ids.json` | 홀드아웃 매니페스트 저장 경로 |

## 출력 구조 (빌드)

```
out_dir/
├── scene.jsonl       # keyframe 한 장당 1개 샘플
├── cut.jsonl         # 컷 내 프레임 시퀀스 단위 샘플 (최대 30장/컷)
├── scenario.jsonl    # 컷 데이터 종합 → 전체 시나리오 샘플
└── images/<video_id>/...  # 학습 이미지 사본
```

각 JSONL 행은 Qwen2.5-VL `messages` 형식 (`{"messages": [{"role": ..., "content": [{"type": "image", ...}, {"type": "text", "text": ...}]}]}`).

## 학습 설정

`configs/` 의 YAML 을 복사·수정해서 사용한다. base 모델, LoRA, 데이터 경로, 하이퍼파라미터를 명시한다.

## 홀드아웃 · before/after 비교

`dataset_builder.build_all()`은 기본적으로 data_dir 내 모든 video_id 를 학습에 쓴다 — 파인튜닝
전후 품질을 비교할 대조군이 없다는 뜻이다. `--holdout_ratio` 로 일부 video_id 를 미리 떼어
`holdout_video_ids.json` 에 기록해두면, 학습 후 그 video_id 들만 base 모델/LoRA 모델 양쪽으로
다시 분석을 돌려 구조 품질을 비교할 수 있다.

```bash
# 1) 홀드아웃 video_id 들을 base 모델로 분석 (기존 output/qwen3.6-cc 등, 이미 있으면 생략)
# 2) 같은 video_id 들을 LoRA 적용해서 재분석
python -m pipeline.cli --llm_backend qwen --qwen_model unsloth/Qwen3.6-35B-A3B \
    --lora_path /data/outputs/20260710/models/qwen3_6_vl_ad --video_id <holdout id>
    # ... holdout_video_ids.json 의 각 id 에 대해 반복

# 3) 구조 품질 비교 (컷 수 일치·필드 완전성·시나리오 완결성)
python -m train_pipeline.compare_outputs \
    --before_dir output/qwen3.6-cc --after_dir output/qwen3.6-cc-lora \
    --holdout_manifest data/holdout_video_ids.json \
    --report_out reports/compare_20260710.json
```

**주의**: `compare_outputs.py`는 `schema_check.py` 기반 **구조 품질**(컷 수 일치·필드 공백·시나리오
완결성)만 비교한다. `check_analysis.py`가 못 잡는 영역(파인튜닝의 실제 주 결함이었던 부분)을
메우기 위한 것이며, 색상·환각 등 **프레임 단위 시각 정확도는 다루지 않는다** — 그건 여전히
사람 또는 LLM 에이전트의 프레임 대조 검수가 필요하다. `--qwen_model`을 base/LoRA 두 실행에
동일하게 맞춰야 한다 (기본값이 `Qwen2.5-VL-7B-Instruct`라서 안 맞추면 "파인튜닝 효과"가 아니라
"모델 크기 차이"를 비교하게 된다).

## Docker 사용법 (GPU 학습 서버)

`train_pipeline/Dockerfile` 은 루트 `Dockerfile`과 별도의 학습 전용 이미지다. Claude Code CLI + unsloth/trl/peft/bitsandbytes 등 LoRA 학습 스택만 담아 가볍게 유지한다 (OCR·STT 등 `pipeline/` 의존성은 포함하지 않음). 베이스는 루트 Dockerfile과 동일한 `pytorch/pytorch:2.12.0-cuda12.6-cudnn9-devel` — CUDA 12.8을 지원하는 드라이버(예: Driver 572.83)와 하위 호환된다.

```bash
# 1) 이미지 빌드 (build context = ad_video_analysis/)
cd ad_video_analysis
docker build -t ad-video-train -f train_pipeline/Dockerfile .

# 2) 컨테이너 실행 — 코드·데이터셋·출력·HF 캐시 마운트, GPU 전달
docker run --rm -it --gpus all \
    -v "$(pwd)":/workspace/ad_video_analysis \
    -v /path/to/data_20260710:/data/data_20260710 \
    -v /path/to/outputs:/data/outputs \
    -v /path/to/hf_cache:/data/.cache/huggingface \
    -w /workspace/ad_video_analysis \
    ad-video-train

# 컨테이너 안에서
claude   # 최초 1회 ANTHROPIC 인증
python -m train_pipeline.cli --config train_pipeline/configs/80gb-3-6-VL-35B-A3B \
    --out_dir /data/outputs/20260710
```

**패키지를 추가/변경할 때**: `train_pipeline/Dockerfile` 의 `pip install` 블록에 반영 (루트 `Dockerfile`/`setup_venv.ps1` 과는 독립적으로 관리).

## venv 사용법 (로컬 Windows)

`ad_video_analysis/setup_venv_train.ps1` (루트에 위치) 은 `train_pipeline` 전용 가상환경(`.venv-train`)을
만든다. 일반 파이프라인 venv(`.venv`)와 분리하는 이유: unsloth가 설치하는 torch/transformers 버전이
OCR·STT 등 일반 파이프라인 의존성과 충돌할 수 있기 때문. `env/python.env` 의 `TRAIN_VENV_PATH` 를 읽는다.

```powershell
.\setup_venv_train.ps1
. .venv-train\Scripts\Activate.ps1
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

Windows에서 `pip install torch`는 CPU 전용 wheel이 기본이라, 스크립트가 CUDA 12.8 인덱스에서
정확한 버전(`torch==2.10.0+cu128`)을 먼저 설치한 뒤 unsloth를 설치한다. unsloth 버전이 올라가
요구하는 torch 버전이 바뀌면 스크립트의 `$torchVersion` 값도 같이 갱신해야 한다 (설치 후
자동으로 CUDA 빌드 유지 여부를 검증해 어긋나면 에러로 알려준다). unsloth/bitsandbytes는
네이티브 Windows에서 불안정할 수 있어, 문제가 생기면 WSL2 또는 `train_pipeline/Dockerfile` 사용을
권장한다.
