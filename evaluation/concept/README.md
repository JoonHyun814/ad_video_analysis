# evaluation/concept

시나리오에서 광고 컨셉을 추출(`concept_evaluation.json`)하고 ChromaDB
`video_concept` 컬렉션과 facet 컬렉션 3개(`ad_target`/`ad_usp`/`ad_creative`)에 적재한다.

## 파일 구성

| 파일 | 역할 |
|------|------|
| `run.py` | CLI 실행기 (`python -m evaluation.cli --mode concept`) |
| `concept_evaluation.py` | 컨셉 추출 프롬프트 빌드 + claude 백엔드 구현 |
| `concept_evaluation_codex.py` / `_gemini.py` / `_qwen.py` | 백엔드별 구현 |
| `concept_vector_store.py` | `video_concept` 컬렉션 upsert/query 헬퍼 |
| `facet_vector_store.py` | facet 컬렉션 3개 upsert/query — 세그먼트 축과 크리에이티브 축을 별도 임베딩으로 나눠 G1~G6 생성 파이프라인이 사용 |

## 출력 스키마 (`concept_evaluation.json`)

- 값만 출력: `industry_category` (13종 enum 중 1~2개 배열), `product_category` (한국어 문자열)
- `{"category": [...], "description": "...", "production_detail": "..."}` 형태 7개 필드:
  `target_persona` / `usp` / `positioning` / `appeal_type` / `perceived_value` /
  `message_strategy` / `execution_style`
- category enum 상세는 `concept_evaluation.py` 및 [`../creative_element_schema.md`](../creative_element_schema.md) 참고

## facet 컬렉션 (`facet_vector_store.py`)

| 컬렉션 | 임베딩 문서 | 용도 |
|--------|-------------|------|
| `ad_target` | `target_persona` 서술 | 타겟이 비슷한 광고 검색 (세그먼트 축) |
| `ad_usp` | `usp` + `positioning` 서술 | USP 가 비슷한 광고 검색 (세그먼트 축) |
| `ad_creative` | `appeal_type`·`execution_style`·`perceived_value`·`message_strategy` 서술 + `production_detail` | 세그먼트 내 분포·군집 분석 = 클리셰 측정 (크리에이티브 축) |

메타데이터는 3개 컬렉션에 동일 복제된다: `video_id`, `product_category`,
`industry_category`(대표값), 7개 필드 대표 category, `genre`
(appeal_type 파생 enum: `humor|emotional|informational|aspirational|urgency|other`).
전체 코퍼스 일괄 적재는 `db/load_facets.py` 사용 ([`../../db/README.md`](../../db/README.md)).

## 실행

```bash
python -m evaluation.cli --mode concept --video_id <ID> [--concept_evaluation] [--load_vector] [--load_facets] [옵션]
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--video_id` | (필수) | 대상 영상 ID |
| `--data_dir` | `output/codex` | `<data_dir>/<video_id>/` 입력·출력 루트 |
| `--concept_evaluation` | off | 컨셉 추출 → `concept_evaluation.json` |
| `--load_vector` | off | `video_concept` 컬렉션에 upsert |
| `--load_facets` | off | facet 컬렉션 3개에 분리 upsert |
| `--db_path` | `output/vector_db` | ChromaDB 저장 경로 |
| `--collection` | `video_concept` | 컬렉션명 |
| `--llm_backend` | `claude` | `claude` \| `codex` \| `qwen` \| `gemini` |
| `--codex_model` / `--qwen_model` / `--gemini_model` | — | 백엔드별 모델명 |

```bash
# 컨셉 추출 + 벡터 적재 한 번에
python -m evaluation.cli --mode concept --video_id 349 --concept_evaluation --load_vector
```
