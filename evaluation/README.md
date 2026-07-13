# evaluation 모듈

시나리오 평가 + 카테고리 메타데이터 추출 + 벡터 DB 적재.

## 파일 구성

| CLI | 역할 |
|------|------|
| `evaluation.cli` | brief 생성 / parsed_analysis 생성 / 시나리오 평가 |
| `evaluation.category_cli` | category_analysis JSON 생성 + ChromaDB 적재 |
| `evaluation.concept_cli` | concept_evaluation JSON 생성 (컨셉 추출) |
| `evaluation.strategy_cli` | scenario_analysis 에서 M1·M2·M3 전략 스키마 역추출 → `strategy_analysis.json` |
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
| `concept_evaluation{,_codex,_gemini,_qwen}.py` | 컨셉 추출 — industry_category·product_category(값만) + target_persona·usp·positioning·appeal_type·perceived_value·message_strategy·execution_style(category·description·production_detail) |
| `vector_store.py` | `video_category` 컬렉션 upsert/query 헬퍼 + 임베딩 모델 (`BAAI/bge-m3`) |
| `concept_vector_store.py` | `video_concept` 컬렉션(별도) upsert/query 헬퍼 — concept_evaluation 결과 전용 |
| `strategy_extraction.py` | scenario_analysis 에서 M1(인사이트)·M2(포지셔닝)·M3(컨셉) 스키마 역추출 (순차 LLM 호출) |
| `strategy_schemas.py` | `docs/m1·m2·m3.txt` 영상 생성 프롬프트의 v5 출력 스키마·역할 가이드 정의 |
| `schemas.py` | 평가/카테고리 JSON 스키마 정의 |
| `scenario_checklist.md` | 시나리오 평가 체크리스트 |
| `docs/m1.txt`·`docs/m2.txt`·`docs/m3.txt` | 영상 생성용 M1~M3 원본 프롬프트 (역추출 스키마의 출처) |

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

## `evaluation.concept_cli` — 컨셉 추출 + 벡터 DB 적재

```bash
python -m evaluation.concept_cli --video_id <ID> [--concept_evaluation] [--load_vector] [옵션]
```

`<data_dir>/<video_id>/scenario_analysis.json` 을 읽어 광고 컨셉을 추출해
`<data_dir>/<video_id>/concept_evaluation.json` 으로 저장한다 (`--concept_evaluation`).
`--load_vector` 는 그 결과를 `video_concept` 컬렉션(카테고리 컬렉션과 별도)에 upsert 한다.

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--data_dir` | `output/codex` | `<data_dir>/<video_id>/` 입력·출력 루트 |
| `--concept_evaluation` | off | 시나리오에서 컨셉 추출 → `concept_evaluation.json` |
| `--load_vector` | off | `concept_evaluation.json` 을 ChromaDB `video_concept` 컬렉션에 upsert |
| `--db_path` | `output/vector_db` | ChromaDB 저장 경로 |
| `--collection` | `video_concept` | 컬렉션명 |
| `--llm_backend` | `claude` | `claude` \| `codex` \| `qwen` \| `gemini` |
| `--codex_model` / `--qwen_model` / `--gemini_model` | — | 백엔드별 모델명 |

```bash
# 컨셉 추출 + 벡터 DB 적재 한 번에
python -m evaluation.concept_cli --video_id 349 --concept_evaluation --load_vector
```

출력 스키마:

- 값만 출력하는 필드:
  - `industry_category`: `beauty`·`food_beverage`·`retail_ecommerce`·`finance`·`healthcare`·`fashion`·
    `tech_electronics`·`automotive`·`entertainment`·`travel`·`education`·`gaming`·`other` 중 1~2개 배열
  - `product_category`: 제품 카테고리 명칭 (한국어 문자열 하나)
- `{"category": [...], "description": "...", "production_detail": "..."}` 형태의 7개 필드
  (`category`는 아래 enum 중 1~2개 배열, `description`은 한국어 줄글 설명, `production_detail`은
  "이 usp를 반영하기 위해 3번째 컷에서 클로즈업을 사용했다"처럼 몇 번째 컷에서 어떤 연출·촬영기법을
  썼는지 구체적으로 서술한 문장):
  - `target_persona`: `category` = `demographic`·`psychographic`·`behavioral`·`other`
  - `usp`: `category` = `functional_tangible`·`emotional_intangible`·`economic_price`·`other`
  - `positioning`: `category` = `by_product_innovation`·`by_service_quality`·`by_cost_leadership`·`by_target_needs`·`other`
  - `appeal_type`: `category` = `humor`·`parody_wordplay`·`maternal_love`·`vanity`·`fear`·`sex_appeal`·`comparison`·
    `rational_info`·`emotional_storytelling`·`testimonial`·`scarcity_urgency`·`nostalgia`·`aspiration`·`other`
    (description에 개사·패러디·언어유희 같은 텍스트 기반 장치를 구체적으로 명시하도록 지시함)
  - `perceived_value`: `category` = `functional_quality`·`functional_price`·`emotional`·`social`·`other`
  - `message_strategy`: `category` = `informational`·`transformational`·`other`
  - `execution_style`: `category` = `slice_of_life`·`scientific_evidence`·`fantasy`·`fashion`·`other`

`video_concept` 컬렉션은 `product_category`·`industry_category`와 위 7개 필드의 `category`·`description`·
`production_detail`을 모두 임베딩 문서로 저장한다. 메타데이터(exact-match 필터용)에는 `product_category`,
`industry_category`(대표값 1개), 7개 필드 각각의 `category` 배열 첫 번째(대표) 값을 저장한다.
`generation.concept_pipeline` (CM3) 이 이 컬렉션을 참고 광고 소스로 사용한다 — 자세한 내용은
[`../generation/README.md`](../generation/README.md) 참고.

## `evaluation.strategy_cli` — M1·M2·M3 전략 스키마 역추출

```bash
python -m evaluation.strategy_cli --video_id <ID> [옵션]
```

`<data_dir>/<video_id>/scenario_analysis.json` 을 읽어, `docs/m1·m2·m3.txt` (영상 생성용 프롬프트)의
v5 출력 스키마와 동일한 구조로 광고 전략을 역추론하고 `<data_dir>/<video_id>/strategy_analysis.json`
하나의 파일에 `{"m1": {...}, "m2": {...}, "m3": {...}}` 형태로 저장한다.

- `m1`: 소비자 인사이트 — corejob·humantruth·culturalcodes·marketscopes·target·forces·triggers·
  opportunitytop3·assumptiontop3·verbatim
- `m2`: 포지셔닝 — messagecandidates·positioningstatement·valueproposition·ownedceps·topcompetitor·
  category·cepcoverage·demandspace·uniqueattributes
- `m3`: 컨셉 발산 — seeds·fixedwhy·concepts (첫 항목 = 광고에 실제 구현된 주 컨셉)

M1 → M2 → M3 순으로 순차 호출하며(뒤 모듈은 앞 모듈 결과를 핸드오프로 받음), 앞 모듈이 실패하면
뒤 모듈은 `{"error": "skipped: ..."}` 로 기록된다.

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--data_dir` | `output/codex` | `<data_dir>/<video_id>/scenario_analysis.json` 입력 루트 |
| `--llm_backend` | `claude` | `claude` \| `codex` \| `gemini` |
| `--codex_model` / `--gemini_model` | — | 백엔드별 모델명 |
| `--timeout` | `600` | 모듈별 LLM 호출 타임아웃(초) |

```bash
python -m evaluation.strategy_cli --video_id 349 --data_dir output/product_plan/claude
```

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
