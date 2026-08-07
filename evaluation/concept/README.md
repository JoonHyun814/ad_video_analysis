# evaluation/concept

[`../strategy/`](../strategy/README.md)가 `scenario_analysis.json` 에서 역추출한
`strategy_analysis.json`(M1 인사이트·M2 포지셔닝·M3 컨셉)을 ChromaDB `ad_concept_reference`
컬렉션에 적재한다 — `generation/v5_m0_m3` M3(컨셉 발산)가 "이 브리프(M0~M2)와 전략적으로
비슷한 기존 광고는 어떤 인간 진실·가치 제안에서 출발해 어떤 전략 렌즈로 컨셉을 만들고
그 why 를 어떻게 증명했는가"를 참고하는 레퍼런스 컬렉션이다. 연출/촬영 디테일은
다루지 않는다 — 그건 [`../creative/README.md`](../creative/README.md)의
`ad_production_reference`(컨셉 확정 후 M5~M9·스토리보드 참고용) 몫이다. 두 컬렉션의 용도
구분은 [`../README.md`](../README.md)의 스키마 통합 계획 참고.

`concept_evaluation.json`(이 폴더의 구 추출 스키마 — flat 카테고리 라벨만 있고 "왜 이
컨셉인가" 인과가 없음)은 더 이상 `ad_concept_reference` 문서 본문에 쓰이지 않는다. 있으면
`db/chromadb/importers/concept_reference.py` 가 세그먼트 필터 보조 카테고리 메타데이터로만
선택적으로 흡수한다(둘 다 없어도 `--load_vector` 는 동작하며, `strategy_analysis.json` 만 필수다).

## 파일 구성

| 파일 | 역할 |
|------|------|
| `run.py` | CLI 실행기 (`python -m evaluation.cli --mode concept`) — `--load_vector` 는 `db/chromadb/importers/concept_reference.py::upsert_concept_reference` 를, `--load_facets` 는 `db/chromadb/importers/facets.py::upsert_facets` 를 호출 |
| `concept_evaluation.py` | 컨셉 추출 프롬프트 빌드 + claude 백엔드 구현 |
| `concept_evaluation_codex.py` / `_gemini.py` / `_qwen.py` | 백엔드별 구현 |

`ad_concept_reference` 컬렉션(upsert/query)과 facet 컬렉션 3개(`ad_target`/`ad_usp`/
`ad_creative`, [`../README.md`](../README.md) 참고 — `generation/segment_retrieval.py` 등
레거시 G1~G6 파이프라인 전용, `ad_concept_reference` 와는 무관)의 실제 로직은
`db/chromadb/importers/concept_reference.py`·`db/chromadb/importers/facets.py` 로 이전됐다
([`../../db/README.md`](../../db/README.md) 참고). 구 `video_concept` 컬렉션
(`concept_vector_store.py`)은 실제 DB 호출 사용처가 없어 삭제됐다 —
`APPEAL_TYPE_CHOICES`/`EXECUTION_STYLE_CHOICES` enum 만 `generation/cliche_report.py`·
`generation/g4_concept_generation.py` 에 인라인으로 남아 있다.

## 출력 스키마 (`concept_evaluation.json`)

- 값만 출력: `industry_category` (13종 enum 중 1~2개 배열), `product_category` (한국어 문자열)
- `{"category": [...], "description": "...", "production_detail": "..."}` 형태 7개 필드:
  `target_persona` / `usp` / `positioning` / `appeal_type` / `perceived_value` /
  `message_strategy` / `execution_style`
- category enum 상세는 `concept_evaluation.py` 및 [`../creative/element_schema.py`](../creative/element_schema.py)(`CONCEPT_INDUSTRY_CATEGORY`/`TARGET_PERSONA_CATEGORY`/`APPEAL_TYPE`/`PERCEIVED_VALUE_CATEGORY`/`MESSAGE_STRATEGY_CATEGORY`/`EXECUTION_STYLE`) 참고

## `ad_concept_reference` 컬렉션 (`db/chromadb/importers/concept_reference.py`)

- **입력**: `<data_dir>/<video_id>/strategy_analysis.json` (필수 — 없으면 `--load_vector` 가 에러로 중단된다. `python -m evaluation.cli --mode strategy` 로 먼저 만든다).
- **문서(임베딩 텍스트)**: m1 `corejob`/`humantruth.truth`/`humantruth.contradiction`, m2 `valueproposition`, m3 선택된 컨셉의 `lens`/`bigidea`/`provingwhy`/`job`/`differentiation`/`risk` 를 라벨과 함께 결합 — "USP/인간 진실이 무엇이기 때문에 이 컨셉·렌즈를 썼는가"의 인과를 그대로 담는다.
- **컨셉 선택**: `strategy_schemas.py` M3_GUIDE 상 `m3.concepts` 는 정확히 1개가 정상(역추출은 발산이 아님). 드물게 여러 개가 나오면(프롬프트 이탈) 이름에 "실구현"/"주 컨셉" 마커가 붙은 것을 우선하고, 없으면 첫 번째를 쓴다(`_select_concept`).
- **메타데이터**: `video_id`, `lens`(9종 전략 렌즈로 정규화 — [`../creative/element_schema.py`](../creative/element_schema.py) `CONCEPT_LENS`, 원문은 자유 텍스트라 `_normalize_lens` 로 키워드 매칭), `claimtag`(`C0`/`C1`/`C2`).
- **레거시 보조 메타데이터(선택)**: 같은 영상 디렉터리에 `concept_evaluation.json`(구 스키마)이 있으면 `industry_category`/`product_category`/`target_persona_category`/`usp_category`/`positioning_category`/`appeal_type`/`perceived_value_category`/`message_strategy_category` 를 세그먼트 필터용으로만 추가한다(문서 본문에는 반영 안 함).
- **크로스 세그먼트 필드(선택)**: 같은 영상 디렉터리에 `creative_element_analysis.json` 이 있으면 `target_gender`/`duration_bucket`/`price_tier` 를 그 `profile` 에서 가져와 함께 심는다(`_run_load_vector` 의 `_enrich_from_creative`).
- **id**: `ad:{video_id}:concept` (영상당 1레코드).

## 실행

```bash
python -m evaluation.cli --mode strategy --video_id <ID> --data_dir <dir>          # 1) strategy_analysis.json 추출
python -m evaluation.cli --mode concept --video_id <ID> --data_dir <dir> --load_vector  # 2) ad_concept_reference 적재
```

`--mode concept` 옵션 (`run.py`):

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--video_id` | (필수) | 대상 영상 ID |
| `--data_dir` | `output/codex` | `<data_dir>/<video_id>/` 입력·출력 루트 |
| `--concept_evaluation` | off | [레거시] `concept_evaluation.json` 추출 — `--load_vector` 문서 본문에는 더 이상 쓰이지 않고, 있으면 세그먼트 필터 보조로만 흡수됨 |
| `--load_vector` | off | `strategy_analysis.json`(필수) + `concept_evaluation.json`/`creative_element_analysis.json`(있으면)을 `ad_concept_reference` 에 upsert |
| `--load_facets` | off | [레거시] facet 컬렉션 3개에 분리 upsert — `ad_concept_reference` 와 무관 |
| `--db_path` | `output/vector_db` | ChromaDB 저장 경로 |
| `--llm_backend` | `claude` | (`--concept_evaluation`/`--load_facets` 전용) `claude` \| `codex` \| `qwen` \| `gemini` |
| `--codex_model` / `--qwen_model` / `--gemini_model` | — | 백엔드별 모델명 |

`--mode strategy` 옵션은 [`../strategy/README.md`](../strategy/README.md) 참고.
