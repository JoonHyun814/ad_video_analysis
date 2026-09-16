# db 모듈

MySQL 조회·CSV 추출 + ChromaDB(벡터 DB) 유틸. **이 저장소의 ChromaDB 접근 코드는 전부
`db/chromadb/` 아래 있다** — 다른 모듈(`evaluation/*`, `generation/*`)은 컬렉션을 직접
적재/조회하지 않고 이 패키지의 함수를 가져다 쓴다.

이 저장소가 구현한 RAG 방식들(Vector/Hybrid/Contextual/Multimodal/Graph/Agentic)의 특징·
장단점·관련 논문은 [`RAG_TYPES.md`](RAG_TYPES.md)에 정리돼 있다.

## 저장 경로 — `data/<컬렉션명>/` 하나로 통일

모든 컬렉션은 `data/<collection>/`에 1:1로 산다(`db.chromadb.connection.db_path_for`) —
`ad_concept_reference`는 `data/ad_concept_reference/`, `category_analysis`는
`data/category_analysis/` 같은 식이다. 폴더명만 보고 바로 어떤 컬렉션인지 알 수 있고,
`db_path`를 명시하지 않으면 이 규칙으로 자동 결정되므로 대부분의 함수·CLI가 `--collection`만
받으면 된다.

| 컬렉션 | 경로 | 적재 주체 |
|--------|------|-----------|
| `video_category` | `data/video_category/` | `evaluation/category/run.py --load_vector` |
| `ad_concept_reference` | `data/ad_concept_reference/` | `evaluation/concept/run.py --load_vector`, `evaluation/ad_concept_production/pipeline.py` |
| `ad_production_reference` | `data/ad_production_reference/` | `evaluation/creative/run.py --load_vector`, `evaluation/ad_concept_production/pipeline.py` |
| `ad_target`/`ad_usp`/`ad_creative` | `data/ad_target/`, `data/ad_usp/`, `data/ad_creative/` | `evaluation/concept/run.py --load_facets` |
| `category_analysis` | `data/category_analysis/` | `db.chromadb.importers.category` |
| `scenario_analysis` | `data/scenario_analysis/` | `db.chromadb.importers.scenario` |
| `ad_visual_reference` | `data/ad_visual_reference/` | `db.chromadb.importers.keyframe_visual` |

## 파일 구성

### MySQL

| 파일 | 역할 |
|------|------|
| `connection.py` | `env/db.env` 를 읽어 MySQL 연결을 열고 닫는 컨텍스트 매니저 |
| `queries.py` | 테이블 목록 조회, 테이블 전체 데이터 조회 |
| `export.py` | 쿼리 결과를 CSV 파일로 저장 |
| `importer.py` | 외부 데이터를 DB로 적재 |
| `cli.py` | MySQL 커맨드라인 진입점 |
| `data_schema.md` | DB 테이블 스키마 |
| `sample.json` | 예시 데이터 |

### ChromaDB — `db/chromadb/`

| 파일 | 역할 |
|------|------|
| `connection.py` | 클라이언트/컬렉션 연결 헬퍼 + 임베딩 함수(`BAAI/bge-m3`) + `db_path_for(collection)`(컬렉션명 → `data/<collection>/`) — 이 저장소의 모든 컬렉션이 공유하는 단일 소스. CLIP 텍스트/이미지 인코더(`get_clip_text_embedding_function`/`get_clip_image_encoder`)도 여기 있음 |
| `list_collections.py` | `data/` 아래 전체 컬렉션 목록 + 레코드 수 출력 |
| `show_schema.py` | 컬렉션 하나 지정 → 메타데이터 스키마(필드·타입·예시) + 데이터 수 출력 |
| `show_by_video_id.py` | 컬렉션 + `video_id` 지정 → 해당 레코드 전체 출력 — `tool_definitions.fetch_by_video_id` 가 재사용 |
| `search_query.py` | 컬렉션 + 자연어 쿼리 지정 → 유사도 상위 레코드 출력(범용) — `tool_definitions.search_chromadb` 가 재사용하는 실제 검색 구현 |
| `hybrid_search.py` | 컬렉션 + 자연어 쿼리 지정 → dense(`search_query.search` 재사용) + BM25 키워드 검색을 RRF 로 결합한 상위 레코드 출력 — `tool_definitions.search_chromadb_hybrid` 가 재사용 |
| `visual_search.py` | `ad_visual_reference` 컬렉션에서 자연어(한국어 포함) 쿼리로 비주얼(이미지) 유사도 검색 — `tool_definitions.search_visual` 가 재사용 |
| `tool_definitions.py` | MCP/Anthropic tool_use 공유 도구 정의. **`search_chromadb` 하나뿐** — 호출마다 `<log_prefix>.jsonl` 에 로그를 남긴다(기본 `logs/search_chromadb/<날짜>/`, `SEARCH_CHROMADB_LOG_DIR` 환경변수로 재지정 가능) |
| `creative_search.py` | `ad_concept_reference`/`ad_production_reference` 의미 검색(세그먼트 필터·self-reference 정책·검색 로그 포함) — RAG 백엔드. `generation/v5_m0_m3 --retrieval`가 이걸 쓴다(도구로는 노출되지 않음, 아래 참고) |
| `mcp_server.py` | `search_chromadb` 하나만 노출하는 stdio MCP 서버(`chromadb-explorer`, 저장소 루트 `.mcp.json` 등록) |
| `importers/category.py` | `<data_root>/<video_id>/category_analysis.json` → `category_analysis` 컬렉션 적재(전체 필드) — 독립 CLI |
| `importers/scenario.py` | `<data_root>/<video_id>/scenario_analysis.json` → `scenario_analysis` 컬렉션 적재(concept/narrative/key_messages/production_notes + cast·scenes 개수) — 독립 CLI |
| `importers/keyframe_visual.py` | `<data_root>/<video_id>/keyframes/*.jpg` → `ad_visual_reference` 컬렉션 적재(CLIP 이미지 임베딩) — 독립 CLI |
| `importers/video_category.py` | `video_category` 컬렉션 적재·검색(`upsert_video`/`upsert_batch`/`query`) — `evaluation/category/run.py --load_vector` 가 쓰는 라이브러리 모듈 |
| `importers/concept_reference.py` | `ad_concept_reference` 컬렉션 적재·조회(`upsert_concept_reference`/`fetch_concepts`) — `evaluation/concept/run.py --load_vector` 가 쓰는 라이브러리 모듈 |
| `importers/facets.py` | `ad_target`/`ad_usp`/`ad_creative` 3개 컬렉션 적재·검색(`upsert_facets`/`query_facet`/`fetch_members`) — `evaluation/concept/run.py --load_facets`, `generation/`의 여러 G1~G6 스크립트가 쓰는 라이브러리 모듈 |
| `importers/production_reference.py` | `ad_production_reference` 컬렉션 적재·조회(`upsert_analysis`/`fetch_profiles`/`fetch_elements`) — `evaluation/creative/run.py --load_vector`, `evaluation/ad_concept_production/pipeline.py` 가 쓰는 라이브러리 모듈 |

`importers/` 안 4개(`video_category.py`/`concept_reference.py`/`facets.py`/`production_reference.py`)는 독립
CLI가 아니라 각 평가 파이프라인의 저장 계층이다 — `evaluation.cli --mode category/concept/creative
--load_vector`가 내부적으로 이 함수들을 호출한다. `category.py`/`scenario.py` 만 자체 `--data_root`
스캔형 CLI(사후 일괄 적재용)다.

## 사전 준비

1. `env/db.env` 에 DB 접속 정보 입력 (MySQL 사용 시)
2. 가상환경 활성화
   ```powershell
   . .venv\Scripts\Activate.ps1
   ```

## DB 연결

- 호스트: `DB_HOST:DB_PORT` (`env/db.env`)
- DB명: `DB_NAME` (`env/db.env`)
- 연결 전 `env/db.env` 를 파싱해서 사용한다 (`connection.py` 가 내부에서 처리).

## 공유폴더 (영상 원본)

- 루트 경로: `ROOT_VIDEO_DIR` (`env/dir.env`)
- DB 의 `video_uploads.file_path` 는 이 경로를 루트로 하는 상대경로.
- 절대경로가 필요할 때는 `ROOT_VIDEO_DIR + file_path` 로 조합한다.

## MySQL — `db.cli`

`ad_video_analysis/` 디렉토리에서 실행한다.

### 테이블 목록 출력

```powershell
python -m db.cli --table_list
```

### 테이블을 CSV로 저장

```powershell
python -m db.cli --save_csv --table_name <테이블명>
# → ./<테이블명>.csv 생성
```

### 옵션 조합

```powershell
python -m db.cli --table_list --save_csv --table_name labeling_data
```

### 코드에서 직접 사용

```python
from pathlib import Path
from db.queries import list_tables, fetch_table
from db.export import save_to_csv

tables = list_tables()
columns, rows = fetch_table("video_uploads")
path = save_to_csv("video_uploads", output_dir=Path("output"))
```

## ChromaDB — `db.chromadb.*` (컬렉션 탐색 유틸)

**어떤 컬렉션이든** 컬렉션명을 인자로 받아 다루는 범용 조회 도구 4개다. `ad_video_analysis/`
디렉토리에서 `python -m db.chromadb.<파일명>` 형태로 실행한다(패키지명이 `chromadb` 라이브러리와
같아 직접 스크립트 실행 시 임포트가 꼬일 수 있으므로 반드시 `-m` 으로 실행한다).

공통 옵션: `--db_path`(미지정 시 `data/<collection>/` 자동 결정), `--json`(JSON 출력).

### 1) 컬렉션(테이블) 목록

```bash
python -m db.chromadb.list_collections
```

`--db_path` 를 안 주면 `data/` 아래 `chroma.sqlite3` 가 있는 디렉터리를 전부 훑어 컬렉션·
레코드 수를 보고한다(컨벤션을 따르지 않는 다른 데이터 폴더는 건드리지 않는다).

### 2) 컬렉션 스키마 + 데이터 수

```bash
python -m db.chromadb.show_schema --collection ad_production_reference [--sample_size 500]
```

ChromaDB 는 고정 스키마가 없으므로, 샘플 레코드의 `metadata` 키를 모아 필드별
타입·예시값·등장 빈도(`coverage`)를 출력한다(레코드 종류에 따라 필드 구성이 다를 수 있음).

### 3) video_id 로 레코드 조회

```bash
python -m db.chromadb.show_by_video_id --collection ad_production_reference --video_id 1
```

`metadata.video_id` 가 일치하는 레코드를 전부 출력한다(한 영상이 여러 레코드로 쪼개져
있는 컬렉션도 있다 — 예: `ad_production_reference` 의 `record_kind=profile`/`element`).

### 4) 자연어 쿼리 유사도 검색

```bash
python -m db.chromadb.search_query --collection ad_concept_reference --query "20대 여성 타겟의 감성적인 라이프스타일 광고" --n_results 5
```

임베딩 모델은 다른 ChromaDB 유틸과 동일한 `BAAI/bge-m3`(`db.chromadb.connection` 소유) —
컬렉션마다 별도 설정이 없다.

### 5) 하이브리드(dense+BM25) 유사도 검색

```bash
python -m db.chromadb.hybrid_search --collection ad_concept_reference --query "컬리 10주년 캠페인" --n_results 5
```

`search_query.py`(dense 단독)의 결과가 브랜드명·숫자·특정 용어 같은 정확 일치 키워드를 의미
유사도에 밀려 놓치는 경우를 보완한다. dense 순위와 BM25 순위를 Reciprocal Rank Fusion(RRF)으로
합쳐 상위 `n_results`건을 반환하고, 각 결과에 `dense_rank`/`bm25_rank`/`rrf_score` 를 함께
표시해 어느 신호로 뽑혔는지 알 수 있게 한다. 형태소 분석기(konlpy/mecab 등)는 쓰지 않고 문자
bigram 토크나이저를 쓴다 — 새 시스템 의존성 없이 한국어 조사 변형에도 부분 매칭되면서, 영문
단어·숫자·브랜드명은 정확 매칭에 가깝게 동작한다.

### 6) 비주얼(이미지) 유사도 검색

```bash
python -m db.chromadb.visual_search --query "보라색 단색 배경" --n_results 5
```

`ad_visual_reference` 컬렉션(`db.chromadb.importers.keyframe_visual` 가 적재)에서 컷 대표
프레임 이미지 자체를 CLIP 임베딩으로 비교한다 — 색감·구도·소품처럼 텍스트 요약에 담기지 않는
순수 시각적 특징을 찾을 때 쓴다. 이미지 인코더는 `clip-ViT-B-32`, 텍스트 인코더는
`clip-ViT-B-32-multilingual-v1`(한국어 포함) — 둘 다 `sentence-transformers` 가 이미
설치돼 있어 새 라이브러리(open-clip 등) 없이 같은 임베딩 공간을 공유한다.

## ChromaDB — `db.chromadb.importers.*` (category/scenario/keyframe_visual 사후 일괄 적재)

`output/total/<video_id>/category_analysis.json`, `scenario_analysis.json`,
`keyframes/*.jpg` 를 스캔해 자연어/이미지 검색용 ChromaDB 컬렉션에 적재한다.

**반드시 `python -m db.chromadb.importers.<파일명>` 형태로 실행한다** — 패키지명이
`chromadb` 라이브러리와 같은 것과 별개로, 이 하위 폴더 자체는 일반 `import` 문으로도 정상
임포트된다(`importers` 는 예약어가 아니다 — 과거 `import/` 로 명명했을 때는 소스 코드에서
`from db.chromadb.import.category import ...` 처럼 점(.) 표기로 직접 임포트할 수 없는 문제가
있어 `importers` 로 이름을 바꿨다).

```bash
python -m db.chromadb.importers.category [--data_root output/total] [--db_path data/category_analysis] [--rebuild]
python -m db.chromadb.importers.scenario [--data_root output/total] [--db_path data/scenario_analysis] [--rebuild]
python -m db.chromadb.importers.keyframe_visual [--data_root output/total] [--db_path data/ad_visual_reference] [--rebuild]
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--data_root` | `output/total` | `<data_root>/<video_id>/*.json`(또는 `keyframes/*.jpg`) 스캔 |
| `--db_path` | `data/category_analysis` \| `data/scenario_analysis` \| `data/ad_visual_reference` | ChromaDB 저장 경로 |
| `--collection` | `category_analysis` \| `scenario_analysis` \| `ad_visual_reference` | 컬렉션명 |
| `--rebuild` | off | 기존 컬렉션 삭제 후 재적재 |

### `category.py` — 적재 내용

`_meta` 를 뺀 `category_analysis.json` 전체 필드(industry_category, product_category,
campaign_objective, placement, target_age_min/max, target_persona, key_message, usp,
positioning, hook_strategy, creative_style, narrative_structure, role_sequence, key_scenes,
duration, brand_name 등)를 `key: value` 줄로 직렬화해 문서 텍스트로 임베딩하고, 동일한
필드를 메타데이터로도 저장한다 — 필드를 고르지 않고 전부 쓰므로 스키마가 늘어나도 코드
수정이 필요 없다.

### `scenario.py` — 적재 내용

`concept`/`narrative`/`key_messages`/`production_notes`(+ `title`/`brand`)만 문서 텍스트로
임베딩한다. `cast`/`scenes` 원문은 넣지 않고 **개수만** `cast_count`/`scenes_count`
메타데이터로 저장한다 — 캐스팅 설명·씬 비트 원문까지 넣으면 문서가 길어져 임베딩 품질이
흐려지기 때문이다.

### `keyframe_visual.py` — 적재 내용

문서 텍스트를 임베딩하지 않는다 — `pipeline/keyframe.py`가 남긴 컷별 대표 프레임
(`cut_XXX_frame_YYYYY.jpg`)을 `clip-ViT-B-32`로 직접 벡터화해 `collection.upsert(embeddings=...)`
로 미리 계산된 벡터를 넣는다. 컬렉션 자체의 `embedding_function`은 검색 시 자연어 쿼리를
인코딩할 `clip-ViT-B-32-multilingual-v1`로 등록해둔다(적재용 이미지 인코더와 검색용 텍스트
인코더가 다르다 — `db/chromadb/connection.py` 참고). 메타데이터는 `video_id`/`cut_index`/
`frame_number`/`image_path`.

## ChromaDB — `db.chromadb.importers.*` (평가 파이프라인 저장 계층)

`video_category.py`/`concept_reference.py`/`facets.py`/`production_reference.py` 는 독립
CLI가 아니라, 평가 파이프라인이 분석 직후 바로 벡터 DB에 적재할 때 쓰는 라이브러리 모듈이다.
`facets.py` 는 컬렉션이 3개(`ad_target`/`ad_usp`/`ad_creative`)라 `db_path` 를 안 주면 facet
마다 각자의 `data/<컬렉션명>/` 을 쓴다(공유 기본값 하나로 셋을 표현할 수 없어서 호출마다 계산).

| 모듈 | 컬렉션 | 호출부 |
|------|--------|--------|
| `video_category.py` | `video_category` | `evaluation/category/run.py --load_vector` |
| `concept_reference.py` | `ad_concept_reference` | `evaluation/concept/run.py --load_vector`, `evaluation/ad_concept_production/pipeline.py` |
| `facets.py` | `ad_target`/`ad_usp`/`ad_creative` | `evaluation/concept/run.py --load_facets`, `generation/`(G1~G6: `cli.py`/`g1_input_normalization.py`/`segment_retrieval.py`/`cliche_report.py`) |
| `production_reference.py` | `ad_production_reference`(`record_kind=profile`/`element`) | `evaluation/creative/run.py --load_vector`, `evaluation/ad_concept_production/pipeline.py` |

각 모듈의 적재 함수(`upsert_*`)는 해당 평가 파이프라인의 `run.py`/`pipeline.py` 안에서만
호출되고, 조회 함수(`fetch_*`/`query_*`)는 `generation/`의 세그먼트 검색·클리셰 집계
스크립트가 쓴다. 자세한 파이프라인 실행 방법은 각 모듈 README
([`../evaluation/category/README.md`](../evaluation/category/README.md),
[`../evaluation/concept/README.md`](../evaluation/concept/README.md),
[`../evaluation/creative/README.md`](../evaluation/creative/README.md)) 참고.

## ChromaDB — `db.chromadb.creative_search` (참조 광고 검색, RAG 백엔드)

`ad_concept_reference`/`ad_production_reference` 두 컬렉션에서 의미 유사도로 참조 광고를
검색한다 — `search_concept_reference`(전략·소구·타겟 참고), `search_production_reference`
(연출·촬영 기법 참고, 대표 크리에이티브 요소 포함). 세그먼트 exact-match 필터
(`list_concept_segment_columns`/`list_production_segment_columns`), self-reference
정책(환경변수 `REFERENCE_RETRIEVAL_SELF_VIDEO_ID`/`REFERENCE_RETRIEVAL_SELF_MODE`), 검색
로그(`REFERENCE_RETRIEVAL_LOG_PATH`/`REFERENCE_RETRIEVAL_LOG_STAGE`)를 포함한다 — 자세한
동작은 모듈 docstring 참고.

**이 모듈의 함수는 MCP 도구로 노출되지 않는다**(아래 "MCP 서버" 절 참고 — `chromadb-explorer`
는 범용 `search_chromadb` 하나만 노출한다). 대신 아래가 코드에서 직접 호출한다(`generation/
retrieval_pipeline` 는 `category_analysis`/`scenario_analysis` 를 LLM 이 자율 판단으로
검색하므로 이 모듈이 아니라 `db.chromadb.tool_definitions`의 범용 `search_chromadb` 도구를
쓴다 — `generation/retrieval_pipeline/tool_chat.py`, 해당 모듈 README 참고):

- `generation/v5_m0_m3/llm_adapter.py --retrieval --llm_backend api` — Anthropic 네이티브
  tool_use 로 `TOOL_DEFINITIONS_CONCEPT`/`TOOL_DEFINITIONS_PRODUCTION`/`call_tool` 을 그대로
  노출(로컬 stdio MCP 서버에 API 가 못 붙어서 MCP 를 거치지 않는 경로). `--llm_backend cli` 는
  MCP(`chromadb-explorer`)의 `search_chromadb` 하나만 쓰므로 segment 필터·self-reference·
  notable_elements 가 없다 — **두 백엔드의 검색 기능이 이제 서로 다르다**([`../generation/v5_m0_m3/README.md`](../generation/v5_m0_m3/README.md) 참고).

## MCP 서버 / Claude API 도구 — `chromadb-explorer`

도구는 **`search_chromadb`/`search_chromadb_hybrid`/`fetch_by_video_id`/`search_visual`/
`search_graph_pattern` 다섯 개**다(검색 네 개는 범용 자연어/비주얼/그래프 검색 — 세그먼트
필터·self-reference 정책 없음; `fetch_by_video_id`는 검색이 아니라 특정 video_id 의 원본 전체
조회다; `search_graph_pattern`은 개별 광고가 아니라 여러 캠페인에 걸친 패턴을 찾는다 — 아래
"Graph" 절 참고). Claude CLI(`claude -p`/대화형 세션)와 Claude API 양쪽에 노출한다. 이
저장소의 유일한 ChromaDB MCP 서버이자, 유일한 Graph(Kùzu) 질의 노출 지점이기도 하다
(`db/graph/`는 저장소가 달라도 같은 MCP 서버 안에서 도구 하나로 노출된다 — 호출하는 쪽은
백엔드가 ChromaDB인지 Kùzu인지 몰라도 된다). `list_collections`/`show_schema`, `importers/*`
(적재 배치 작업)는 도구로 올리지 않는다 — 사람이 CLI로 직접 실행한다.

| 도구 | 인자 | 반환 |
|------|------|------|
| `search_chromadb` | `collection`(필수), `query_text`(필수, 자연어), `n_results`(기본 5), `log_prefix`(기본 `"default"`) | dense 유사도 상위 레코드 |
| `search_chromadb_hybrid` | 위와 동일 | dense+BM25 RRF 결합 상위 레코드(`dense_rank`/`bm25_rank`/`rrf_score` 포함) — 브랜드명·숫자 등 정확 매칭 키워드가 있을 때 우선 사용 |
| `fetch_by_video_id` | `collection`(필수), `video_id`(필수, integer), `log_prefix`(기본 `"default"`) | 해당 video_id 의 레코드 전체(청킹 우회, Contextual/Long-context RAG) — 검색으로 이미 찾은 광고의 원본이 필요할 때만 사용 |
| `search_visual` | `query_text`(필수, 자연어), `n_results`(기본 5), `collection`(기본 `ad_visual_reference`), `log_prefix`(기본 `"default"`) | 키프레임 이미지를 CLIP 으로 비교한 상위 레코드(`video_id`/`cut_index`/`image_path`) — 이미지 파일 자체는 반환하지 않는다 |
| `search_graph_pattern` | `role`(필수), `persona_category`(선택), `top_k`(기본 10), `log_prefix`(기본 `"default"`) | 그 역할(role)에서 자주 쓰인 `element_type`/`element_subtype` 집계(Graph RAG, 캠페인 간 패턴) |

`db_path` 를 도구 인자로 받지 않는다 — `collection` 명만 주면 `data/<collection>/` 로 자동
결정된다(호출하는 쪽이 내부 폴더 구조를 몰라도 됨).

**호출 로깅(항상 켜짐)**: 호출마다 `<log_root>/<log_prefix>.jsonl` 에 한 줄씩 append 된다
(`{"timestamp","backend","collection","query_text","n_results","result_count","results"}` —
`backend` 는 `"dense"`(search_chromadb)/`"hybrid"`(search_chromadb_hybrid)/
`"fetch_by_video_id"`/`"visual"`(search_visual)/`"graph"`(search_graph_pattern) 다섯 가지,
`fetch_by_video_id` 로그는 `query_text`/`n_results` 대신 `video_id` 필드를, `search_graph_pattern`
로그는 `query_text` 자리에 `"role=... persona=..."` 조합 문자열을 남긴다. 검색 결과 원본도
함께 남는다). `log_prefix` 로 호출 맥락(프로젝트/단계명 등)을 구분해서 기록한다 —
미지정 시 `default.jsonl` 로 몰린다. `log_root` 는 기본 `logs/search_chromadb/<날짜>/`
(하루 단위 폴더 — 한 파일에 로그가 무한정 쌓이지 않도록)지만 `SEARCH_CHROMADB_LOG_DIR`
환경변수로 호출측이 재지정할 수 있다(도구 스키마에는 없다 — LLM 이 저장 위치를 결정하지
않도록). 재지정 시에는 그 경로를 그대로 쓰고 날짜 폴더를 추가로 끼워 넣지 않는다(재지정한
경로에 이미 날짜가 있다고 간주). `generation/v5_m0_m3/llm_adapter.py` 는 stage 명
(`M3`/`M4`.../`STORYBOARD_HTML`)을 `log_prefix` 로 자동 지정해 단계별로 로그 파일이 나뉘고
(`log_root` 는 기본값 그대로 씀), `generation/retrieval_pipeline`(`tool_chat.py`)는
`log_prefix` 를 프로젝트 제목으로, `log_root` 를 그 실행의 출력 폴더로 지정한다
([`../generation/retrieval_pipeline/README.md`](../generation/retrieval_pipeline/README.md) 참고).

**Claude CLI(MCP)**: 저장소 루트 `.mcp.json`에 `chromadb-explorer` 로 등록돼 있다.

```bash
python -m db.chromadb.mcp_server   # 로컬 실행/디버그
claude -p "..." --mcp-config .mcp.json --allowedTools "mcp__chromadb-explorer__search_chromadb"
```

`claude -p` 헤드리스 호출로 쓰려면 최초 1회 승인이 필요하다 — 로컬 `.claude/settings.json`
(개인 상태, `.gitignore` 로 제외)에 `{"enabledMcpjsonServers": ["chromadb-explorer"]}` 를 넣거나
프로젝트 디렉터리에서 `claude` 를 한 번 대화형으로 실행해 승인한다.

**Claude API(Anthropic tool_use)**: 로컬 stdio MCP 서버에 API 가 직접 붙을 수 없으므로(원격
HTTP/SSE MCP 커넥터만 지원), `db.chromadb.tool_definitions.TOOL_DEFINITIONS`/`call_tool` 을
그대로 가져다 `messages.create(..., tools=...)` 호출과 tool_use 왕복 루프에 쓴다.

**내부망 원격 접속(Streamable HTTP)**: 같은 `search_chromadb` 도구를 로컬 subprocess 없이
내부망의 다른 머신·Anthropic API 원격 MCP 커넥터에 노출하려면 `server/mcp_server.py`(병행
운영되는 별도 서버, `python -m server.mcp_server`)를 쓴다 — 자세한 내용은
[`../server/README.md`](../server/README.md) 참고.

**임베딩 모델 예열**: `mcp_server.py` 는 `__main__` 실행 시 `connection.get_embedding_function()`
으로 bge-m3 를 서버 기동 시점에 미리 로드한다(`search_chromadb` 는 임의의 컬렉션을 검색하므로
특정 컬렉션이 아니라 임베딩 함수 자체만 예열한다) — 그렇지 않으면 첫 검색 호출이 모델 로딩
비용까지 떠안아 느려지거나 타임아웃에 걸릴 수 있다.

## Graph — `db.graph.*` (Kùzu, 관계·서사 구조 추론)

`data/ad_visual_reference/` 등과 달리 **ChromaDB 컬렉션이 아니다** — `data/ad_graph/`는
[Kùzu](https://kuzudb.com/)(임베디드 그래프 DB, 별도 서버 프로세스 없음) 파일이다. 지금까지의
검색(dense/hybrid/visual)은 "쿼리 하나 → 유사 레코드 목록"만 가능한데, "여러 캠페인에 걸친
서사 역할별 크리에이티브 요소 패턴"처럼 다단(multi-hop) 관계 질의는 그래프가 아니면 어렵다.

### 노드/엣지 스키마

| 노드 | 기본키 | 속성 |
|------|--------|------|
| `Campaign` | `video_id` | `brand_name`, `industry_category`, `product_category`, `campaign_objective`, `duration` |
| `Sequence` | `id`(`"<video_id>:seq:<position>"`) | `video_id`, `position`, `role`, `cut_index` |
| `Element` | `id`(ChromaDB 레코드 id 재사용) | `video_id`, `element_type`, `element_subtype`, `description`, `cut_refs` |
| `Persona` | `category` | (dedup 노드 — 여러 캠페인이 같은 페르소나를 공유) |

| 엣지 | 방향 | 속성 |
|------|------|------|
| `HAS_TARGET_PERSONA` | Campaign → Persona | — |
| `HAS_SEQUENCE` | Campaign → Sequence | `position` |
| `INCLUDES_ELEMENT` | Sequence → Element | — |
| `TRANSITIONS_TO` | Element → Element | — |

### 데이터 소스와 한계

원본 JSON(`category_analysis.json`/`scenario_analysis.json`/`production_analysis.json`)을
다시 스캔하지 않는다 — `category_analysis`/`ad_production_reference`(`record_kind=element`)/
`ad_concept_reference` 세 ChromaDB 컬렉션을 읽어 그래프를 만든다(각각 `category.py`/
`production_reference.py`/`concept_reference.py`가 이미 정규화해둔 데이터 재사용).

`role_sequence`(`category_analysis.json`, 쉼표 구분 문자열)는 `scenario_analysis.json`의
`cut_index`와 형식적으로 연결돼 있지 않다 — **i번째 역할을 그 캠페인 Element 들의 `cut_refs`
합집합에서 i번째로 작은 `cut_index`에 위치적으로 대응**시킨다(LLM이 "씬 순서별로" 역할을
나열하라는 프롬프트 지시를 실제로 따랐다는 best-effort 가정 — 강제되지 않으므로 개별 캠페인에
따라 어긋날 수 있다). `TRANSITIONS_TO`는 같은 `video_id` + 같은 `element_type` 안에서
`cut_refs` 최솟값 기준 오름차순으로 연속된 Element 를 잇는다.

**다음 확장(미구현)**: `SIMILAR_TO`(Campaign↔Campaign, `search_chromadb` 벡터 유사도를 그래프에
역주입해 "이 캠페인과 비슷한 다른 캠페인" 다단 탐색을 가능하게 함).

### 파일 구성

| 파일 | 역할 |
|------|------|
| `connection.py` | Kùzu 연결 헬퍼(`data/ad_graph/`, `db.chromadb.connection.db_path_for` 재사용) |
| `schema.py` | 노드/엣지 테이블 DDL, `ensure_schema()`(존재하면 조용히 건너뜀) |
| `importers/campaign_graph.py` | 위 세 ChromaDB 컬렉션 → 그래프 적재 — 독립 CLI |
| `graph_query.py` | `role_element_frequency()`(도구로 노출) + `campaign_graph()`(CLI 전용) |

### CLI

```bash
python -m db.graph.importers.campaign_graph [--rebuild]
python -m db.graph.graph_query --role HOOK [--persona <카테고리>] [--top_k 10]
python -m db.graph.graph_query --video_id <id>   # campaign_graph() — 특정 캠페인 전체 조회
```

`search_chromadb`처럼 원시 Cypher 를 도구로 노출하지 않는다 — `role_element_frequency()` 만
`search_graph_pattern` 도구로 올라간다("MCP 서버 / Claude API 도구" 절 참고). `campaign_graph()`
는 `list_collections`/`show_schema`와 같은 취급으로 CLI 전용이다.
