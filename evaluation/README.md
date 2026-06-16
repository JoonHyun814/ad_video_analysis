# evaluation 모듈

시나리오 평가 + 카테고리 메타데이터 추출 + 벡터 DB 적재.

## 파일 구성

| CLI | 역할 |
|------|------|
| `evaluation.cli` | brief 생성 / parsed_analysis 생성 / 시나리오 평가 |
| `evaluation.category_cli` | category_analysis JSON 생성 + ChromaDB 적재 |
| `evaluation.convert` | parsed/brief JSON 을 외부 시스템 스키마로 변환 |

핵심 모듈:

| 파일 | 역할 |
|------|------|
| `brief_generator{,_codex,_gemini,_qwen}.py` | 시나리오에서 브리프 추출 (백엔드별) |
| `parsed_analysis{,_codex,_gemini,_qwen}.py` | 분석 결과 종합 |
| `evaluator{,_codex,_gemini,_qwen}.py` | 시나리오 평가 (브리프 비교 포함/제외) |
| `category_analysis{,_codex,_gemini}.py` | 카테고리 메타데이터 추출 |
| `vector_store.py` | ChromaDB upsert/query 헬퍼 + 임베딩 모델 (`BAAI/bge-m3`) |
| `schemas.py` | 평가/카테고리 JSON 스키마 정의 |
| `scenario_checklist.md` | 시나리오 평가 체크리스트 |

## `evaluation.cli` — 평가 파이프라인

```bash
python -m evaluation.cli --video_id <ID> [--brief] [--parsed_analysis] [--scenario_evaluation] [옵션]
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--data_dir` | `output/codex` | `<data_dir>/<video_id>/` 입력 루트 |
| `--output_dir` | = `--data_dir` | brief/parsed 결과 저장 루트 |
| `--brief` | off | `scenario_analysis.json` → `brief_analysis.json` |
| `--parsed_analysis` | off | scenario/cuts/cut_analysis/scene_analysis/stt/audio → `parsed_analysis.json` |
| `--scenario_evaluation` | off | brief 가 있으면 비교 포함, 없으면 단독 평가 → `evaluation.json` |
| `--llm_backend` | `claude` | `claude` \| `codex` \| `qwen` \| `gemini` |
| `--codex_model` / `--qwen_model` / `--gemini_model` | — | 백엔드별 모델명 |

```bash
# 브리프 + 시나리오 평가
python -m evaluation.cli --video_id 349 --brief --scenario_evaluation

# Gemini 백엔드로 parsed_analysis 만
python -m evaluation.cli --video_id 349 --parsed_analysis --llm_backend gemini
```

## `evaluation.category_cli` — 카테고리 분석 + 벡터 DB 적재

```bash
python -m evaluation.category_cli --video_id <ID> [--category_analysis] [--load_vector] [옵션]
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--data_dir` | `output/product_plan/claude` | `<data_dir>/<video_id>/scenario_analysis.json` 입력 |
| `--category_analysis` | off | 시나리오에서 카테고리 메타데이터 추출 → `category_analysis.json` |
| `--load_vector` | off | `category_analysis.json` 을 ChromaDB 에 upsert |
| `--db_path` | `output/vector_db` | ChromaDB 저장 경로 |
| `--collection` | `video_category` | 컬렉션명 |
| `--llm_backend` | `claude` | `claude` \| `codex` \| `gemini` |

```bash
# 카테고리 분석 + 벡터 DB 적재 한 번에
python -m evaluation.category_cli --video_id 349 --category_analysis --load_vector \
    --data_dir output/additional_0609/claude
```

> 임베딩 모델: `BAAI/bge-m3` (1024-dim, 한/영 cross-lingual). 변경 시 `evaluation/vector_store.py::EMBEDDING_MODEL` 수정 후 `python db/reembed.py` 로 재적재. 자세한 검색 사용법은 [`../db/README.md`](../db/README.md) 참고.

## `evaluation.convert` — 외부 스키마 변환

```bash
python -m evaluation.convert --video_dir <루트> --out_dir <저장경로> [--mode parsed|brief]
```

`<video_dir>/<id>/` 안의 분석 결과를 모아 `<out_dir>/<id>.json` 으로 저장한다.
- `--mode parsed` (기본): `parsed_analysis.json` → `claude_preprocessed_v1` 스키마
- `--mode brief`: `brief_analysis.json` → 그대로 저장
