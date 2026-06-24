# evaluation 모듈

시나리오 평가 + 카테고리 메타데이터 추출 + 벡터 DB 적재.

## 파일 구성

| CLI | 역할 |
|------|------|
| `evaluation.cli` | brief 생성 / parsed_analysis 생성 / 시나리오 평가 |
| `evaluation.category_cli` | category_analysis JSON 생성 + ChromaDB 적재 |
| `evaluation.convert` | parsed/brief JSON 을 외부 시스템 스키마로 변환 |
| `evaluation.convert_v2` | parsed_analysis 를 그대로 `parsed` 키로 감싼 wrapped 스키마 변환 |
| `evaluation.rename_to_original` | `<id>.json` 결과 파일을 DB `video_uploads.original_filename` 기준으로 재명명 복사 |

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

## `evaluation.convert_v2` — wrapped 스키마 변환

```bash
python -m evaluation.convert_v2 --video_dir <루트> --out_dir <저장경로>
```

`parsed_analysis.json` 을 가공 없이 `parsed` 키로 감싸고, 상위에 VideoLabelingTool 호환
메타(`video_id`, `original_filename`, `model_cuts`, `parse_success`, `human_label`, `match` 등)를
부여한다. `model_cuts` 은 `parsed.cuts` 의 `cut_id/start_sec/end_sec` 에서 추린다.

## `evaluation.rename_to_original` — DB original_filename 으로 재명명

```bash
python -m evaluation.rename_to_original --video_dir <입력> --out_dir <저장경로>
```

`<video_dir>/<id>.json` 파일들을 DB `video_uploads.original_filename` 기준으로 복사·재명명한다.
확장자는 `.json` 으로 교체되며, Windows 금지문자(`<>:"/\\|?*`)는 `_` 로 살균된다. DB 는 IN 쿼리
1회로 일괄 조회하며, 같은 이름 충돌 시 `__<video_id>` 접미사를 자동 부여한다.
