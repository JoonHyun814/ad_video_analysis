# train_pipeline 모듈

`pipeline` 분석 결과를 Qwen VL 학습용 JSONL 데이터셋으로 빌드하고, YAML 설정으로 학습을 실행한다.

## 파일 구성

| 파일 | 역할 |
|------|------|
| `cli.py` | 데이터셋 빌드 / 학습 진입점 |
| `dataset_builder.py` | scene·cut·scenario 3종 JSONL 빌드 + 이미지 사본 |
| `trainer.py` | YAML 설정 로드 + 학습 루프 |
| `configs/` | 학습 설정 YAML 샘플 |
| `Dockerfile` | 학습 전용 이미지 (Claude Code + unsloth LoRA 학습 스택) |

## 사용법

```bash
# 1) 데이터셋 빌드
python -m train_pipeline.cli --build_dataset --data_dir output/ [output2/ ...] --out_dir data/

# 2) 학습
python -m train_pipeline.cli --config configs/sample --out_dir runs/exp1
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--build_dataset` | — | 데이터셋 빌드 모드 (`--config` 와 상호 배타) |
| `--config` | — | 학습 모드. YAML 경로 (`.yaml` 자동 보강) |
| `--data_dir` | `output/` | 분석 결과 루트 (여러 경로 가능) |
| `--out_dir` | (필수) | 빌드/학습 결과 저장 디렉토리 |

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
