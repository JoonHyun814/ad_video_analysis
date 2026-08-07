# db 모듈

MySQL 조회·CSV 추출 + ChromaDB(벡터 DB) 유틸. **이 저장소의 ChromaDB 접근 코드는 전부
`db/chromadb/` 아래 있다** — 다른 모듈(`evaluation/*`, `generation/*`)은 컬렉션을 직접
적재/조회하지 않고 이 패키지의 함수를 가져다 쓴다.

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
| `connection.py` | 클라이언트/컬렉션 연결 헬퍼 + 임베딩 함수(`BAAI/bge-m3`) + `db_path_for(collection)`(컬렉션명 → `data/<collection>/`) — 이 저장소의 모든 컬렉션이 공유하는 단일 소스 |
| `list_collections.py` | `data/` 아래 전체 컬렉션 목록 + 레코드 수 출력 |
| `show_schema.py` | 컬렉션 하나 지정 → 메타데이터 스키마(필드·타입·예시) + 데이터 수 출력 |
| `show_by_video_id.py` | 컬렉션 + `video_id` 지정 → 해당 레코드 전체 출력 |
| `search_query.py` | 컬렉션 + 자연어 쿼리 지정 → 유사도 상위 레코드 출력(범용) — `tool_definitions.search_chromadb` 가 재사용하는 실제 검색 구현 |
| `tool_definitions.py` | MCP/Anthropic tool_use 공유 도구 정의. **`search_chromadb` 하나뿐** — 호출마다 `logs/search_chromadb/<log_prefix>.jsonl` 에 로그를 남긴다 |
| `creative_search.py` | `ad_concept_reference`/`ad_production_reference` 의미 검색(세그먼트 필터·self-reference 정책·검색 로그 포함) — RAG 백엔드. `generation/retrieval_pipeline`·`generation/v5_m0_m3 --retrieval`가 이걸 쓴다(도구로는 노출되지 않음, 아래 참고) |
| `mcp_server.py` | `search_chromadb` 하나만 노출하는 stdio MCP 서버(`chromadb-explorer`, 저장소 루트 `.mcp.json` 등록) |
| `importers/category.py` | `<data_root>/<video_id>/category_analysis.json` → `category_analysis` 컬렉션 적재(전체 필드) — 독립 CLI |
| `importers/scenario.py` | `<data_root>/<video_id>/scenario_analysis.json` → `scenario_analysis` 컬렉션 적재(concept/narrative/key_messages/production_notes + cast·scenes 개수) — 독립 CLI |
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

## ChromaDB — `db.chromadb.importers.*` (category/scenario 사후 일괄 적재)

`output/total/<video_id>/category_analysis.json`, `scenario_analysis.json` 을 스캔해
자연어 검색용 ChromaDB 컬렉션에 적재한다.

**반드시 `python -m db.chromadb.importers.<파일명>` 형태로 실행한다** — 패키지명이
`chromadb` 라이브러리와 같은 것과 별개로, 이 하위 폴더 자체는 일반 `import` 문으로도 정상
임포트된다(`importers` 는 예약어가 아니다 — 과거 `import/` 로 명명했을 때는 소스 코드에서
`from db.chromadb.import.category import ...` 처럼 점(.) 표기로 직접 임포트할 수 없는 문제가
있어 `importers` 로 이름을 바꿨다).

```bash
python -m db.chromadb.importers.category [--data_root output/total] [--db_path data/category_analysis] [--rebuild]
python -m db.chromadb.importers.scenario [--data_root output/total] [--db_path data/scenario_analysis] [--rebuild]
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--data_root` | `output/total` | `<data_root>/<video_id>/*.json` 스캔 |
| `--db_path` | `data/category_analysis` \| `data/scenario_analysis` | ChromaDB 저장 경로 |
| `--collection` | `category_analysis` \| `scenario_analysis` | 컬렉션명 |
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
는 범용 `search_chromadb` 하나만 노출한다). 대신 두 곳이 코드에서 직접 호출한다:

- `generation/retrieval_pipeline/retrieval.py` — M5(결정적 검색 실행)가 직접 호출
- `generation/v5_m0_m3/llm_adapter.py --retrieval --llm_backend api` — Anthropic 네이티브
  tool_use 로 `TOOL_DEFINITIONS_CONCEPT`/`TOOL_DEFINITIONS_PRODUCTION`/`call_tool` 을 그대로
  노출(로컬 stdio MCP 서버에 API 가 못 붙어서 MCP 를 거치지 않는 경로). `--llm_backend cli` 는
  MCP(`chromadb-explorer`)의 `search_chromadb` 하나만 쓰므로 segment 필터·self-reference·
  notable_elements 가 없다 — **두 백엔드의 검색 기능이 이제 서로 다르다**([`../generation/v5_m0_m3/README.md`](../generation/v5_m0_m3/README.md) 참고).

## MCP 서버 / Claude API 도구 — `chromadb-explorer`

도구는 **`search_chromadb` 하나뿐**이다(범용 자연어 검색 — 세그먼트 필터·self-reference
정책 없음). Claude CLI(`claude -p`/대화형 세션)와 Claude API 양쪽에 노출한다. 이 저장소의
유일한 ChromaDB MCP 서버다. `list_collections`/`show_schema`/`show_by_video_id`,
`importers/*`(컬렉션 삭제·재적재 배치 작업)는 도구로 올리지 않는다 — 사람이 CLI로 직접
실행한다.

| 도구 | 인자 | 반환 |
|------|------|------|
| `search_chromadb` | `collection`(필수), `query_text`(필수, 자연어), `n_results`(기본 5), `log_prefix`(기본 `"default"`) | 유사도 상위 레코드 |

`db_path` 를 도구 인자로 받지 않는다 — `collection` 명만 주면 `data/<collection>/` 로 자동
결정된다(호출하는 쪽이 내부 폴더 구조를 몰라도 됨).

**호출 로깅(항상 켜짐)**: 호출마다 `logs/search_chromadb/<log_prefix>.jsonl` 에 한 줄씩
append 된다(`{"timestamp","collection","query_text","n_results","result_count"}`). `log_prefix`
로 호출 맥락(프로젝트/단계명 등)을 구분해서 기록한다 — 미지정 시 `logs/search_chromadb/default.jsonl`
로 몰린다. `generation/v5_m0_m3/llm_adapter.py` 는 stage 명(`M3`/`M4`.../`STORYBOARD_HTML`)을
`log_prefix` 로 자동 지정해 단계별로 로그 파일이 나뉜다.

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

**임베딩 모델 예열**: `mcp_server.py` 는 `__main__` 실행 시 `connection.get_embedding_function()`
으로 bge-m3 를 서버 기동 시점에 미리 로드한다(`search_chromadb` 는 임의의 컬렉션을 검색하므로
특정 컬렉션이 아니라 임베딩 함수 자체만 예열한다) — 그렇지 않으면 첫 검색 호출이 모델 로딩
비용까지 떠안아 느려지거나 타임아웃에 걸릴 수 있다.
