# mapping_pipeline 모듈

DB 에 등록되지 않은 외부 영상 + 시나리오 텍스트를 받아 컷 감지 → cut_analysis → cut-scene 매핑을 수행한다. CLI / FastAPI / Gradio 3가지 인터페이스 제공.

## 파일 구성

| 파일 | 역할 |
|------|------|
| `cli.py` | 커맨드라인 진입점 |
| `runner.py` | 컷 감지 + 매핑 오케스트레이션 (FastAPI 와 공유) |
| `cut_mapper.py` | cut_analysis 결과 + 시나리오 텍스트 → Gemini 로 cut-scene 매핑 |
| `cut_mapper_openai.py` | cut_analysis 결과 + 시나리오 텍스트 → OpenAI 로 cut-scene 매핑 |
| `api.py` | FastAPI 서버 (`POST /analyze`) |
| `gradio_app.py` | Gradio 웹 데모 |
| `API.md` | FastAPI 스펙 문서 |
| `curl_examples.sh` | API curl 호출 예시 |

## CLI

```bash
python -m mapping_pipeline.cli --video_path <영상.mp4> --scenario_path <시나리오.txt|json> [옵션]
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--video_path` | (필수) | 영상 파일 |
| `--scenario_path` | (필수) | 시나리오 텍스트 또는 JSON |
| `--out_dir` | `output/<video_stem>` | 결과 저장 |
| `--backend` | `transnetv2` | `transnetv2` \| `scenedetect` |
| `--llm_backend` | `openai` | `gemini` \| `openai` |
| `--llm_model` | 백엔드 기본값 | LLM 모델명 (gemini=`models/gemini-2.5-flash-lite`, openai=`gpt-4o-mini`) |
| `--max_cuts` | `10` | 최대 컷 수 |
| `--threshold` | 백엔드 기본 | 컷 감지 민감도 |
| `--skip_preprocess` | off | 전처리(컷 감지·프레임) 건너뜀 (캐시 재사용) |
| `--skip_cut_analysis` | off | cut_analysis 건너뜀 (캐시 재사용) |

### 사용 예시

```bash
# Gemini (기본)
python -m mapping_pipeline.cli --video_path video.mp4 --scenario_path scenario.txt

# OpenAI
python -m mapping_pipeline.cli --video_path video.mp4 --scenario_path scenario.txt \
  --llm_backend openai --llm_model gpt-4o
```

출력: `out_dir/{cuts,cut_analysis,cut_scene_mapping}.json` + `keyframes/`, `frames/`.

## FastAPI 서버

```bash
python mapping_pipeline/api.py [PORT]   # 기본 8000
```

엔드포인트:
- `GET /health` — 상태 확인
- `POST /analyze` — multipart 업로드 (`video_file` + `scenario_file` 또는 `scenario_text`)

추가 Form 파라미터: `llm_backend` (`gemini`|`openai`), `llm_model` (기본값: 백엔드별 기본 모델)

스펙 상세는 [`API.md`](API.md), curl 예시는 [`curl_examples.sh`](curl_examples.sh).

## Gradio 데모

```bash
python mapping_pipeline/gradio_app.py
```

LLM 백엔드(Gemini / OpenAI)와 모델명을 UI에서 선택할 수 있다.

## 환경 변수

| 키 | 파일 | 용도 |
|----|------|------|
| `GEMINI_API_KEY` | `env/api.env` | Gemini 백엔드 사용 시 필수 |
| `OPENAI_API_KEY` | `env/api.env` | OpenAI 백엔드 사용 시 필수 |
