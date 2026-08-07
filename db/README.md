# db 모듈

MySQL 조회·CSV 추출 + ChromaDB 벡터 검색·재임베딩 유틸.

## 파일 구성

| 파일 | 역할 |
|------|------|
| `connection.py` | `env/db.env` 를 읽어 MySQL 연결을 열고 닫는 컨텍스트 매니저 |
| `queries.py` | 테이블 목록 조회, 테이블 전체 데이터 조회 |
| `export.py` | 쿼리 결과를 CSV 파일로 저장 |
| `importer.py` | 외부 데이터를 DB로 적재 |
| `cli.py` | MySQL 커맨드라인 진입점 |
| `chromadb_search.py` | 카테고리 벡터 유사도 검색 CLI |
| `chromadb_show.py` | 컬렉션 내 전체 레코드 출력 |
| `chromadb_missing.py` | `video_uploads` 와 ChromaDB id 비교 (DB - vector) |
| `reembed.py` | 임베딩 모델 교체 후 컬렉션 재적재 |
| `load_facets.py` | concept_evaluation.json → facet 컬렉션 3개(`ad_target`/`ad_usp`/`ad_creative`) 일괄 적재 |
| `cluster.py` | 컬렉션 임베딩 K-Means 클러스터링 (K 자동 선택) |
| `product_research.py` | 제품명 웹검색 조사 → category/usp/target 프로필 |
| `ad_retrieval.py` | `ad_production_reference`(creative vector db, record_kind=profile) 유사도 검색 |
| `cliche_twist_analysis.py` | 검색 결과 세그먼트 클리셰 집계 + 비튼 광고 판별 |
| `cliche_twist_format.py` | 위 결과를 txt 리포트로 포맷 |
| `product_cliche_search.py` | 제품명 → 리서치 + 유사광고 검색 + 클리셰 비틀기 분석 CLI 진입점 |
| `chromadb/connection.py` | `db_path` → PersistentClient / 컬렉션 연결 공용 헬퍼(임베딩 함수 부착 여부 선택) |
| `chromadb/list_collections.py` | 컬렉션(테이블) 목록 + 레코드 수 출력 |
| `chromadb/show_schema.py` | 컬렉션 하나 지정 → 메타데이터 스키마(필드·타입·예시) + 데이터 수 출력 |
| `chromadb/show_by_video_id.py` | 컬렉션 + `video_id` 지정 → 해당 레코드 전체 출력 |
| `chromadb/search_query.py` | 컬렉션 + 자연어 쿼리 지정 → 유사도 상위 레코드 출력 |
| `chromadb/import/category.py` | `<data_root>/<video_id>/category_analysis.json` → `data/category` 컬렉션 적재(전체 필드) |
| `chromadb/import/scenario.py` | `<data_root>/<video_id>/scenario_analysis.json` → `data/scenario` 컬렉션 적재(concept/narrative/key_messages/production_notes + cast·scenes 개수) |
| `chromadb/tool_definitions.py` | 조회 유틸 4종을 Anthropic tool_use 스키마(`TOOL_DEFINITIONS`)+디스패처(`call_tool`)로 감싼 공유 모듈(저장소 자동 탐색 포함) — MCP 서버와 API 백엔드가 공유 |
| `chromadb/mcp_server.py` | 위 유틸을 MCP 도구로 노출하는 stdio MCP 서버(`chromadb-explorer`, 저장소 루트 `.mcp.json` 등록) |
| `data_schema.md` | DB 테이블 스키마 |
| `sample.json` | 예시 데이터 |

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

`chromadb_search.py`/`chromadb_show.py`(단일 `video_category` 컬렉션 전용)와 달리, 이 4개는
**어떤 컬렉션이든** 컬렉션명을 인자로 받아 다룬다. `ad_video_analysis/` 디렉토리에서
`python -m db.chromadb.<파일명>` 형태로 실행한다(패키지명이 `chromadb` 라이브러리와 같아
직접 스크립트 실행 시 임포트가 꼬일 수 있으므로 반드시 `-m` 으로 실행한다).

공통 옵션: `--db_path`(기본 `output/vector_db`), `--json`(JSON 출력).

### 1) 컬렉션(테이블) 목록

```bash
python -m db.chromadb.list_collections
```

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

임베딩 모델은 다른 ChromaDB 유틸과 동일한 `BAAI/bge-m3`(`evaluation/category/vector_store.py`
재사용) — 컬렉션마다 별도 설정이 없다.

## ChromaDB — `db.chromadb.import.*` (category/scenario 적재)

`output/total/<video_id>/category_analysis.json`, `scenario_analysis.json` 을 스캔해
자연어 검색용 ChromaDB 컬렉션에 적재한다. 다른 ChromaDB 유틸과 달리 **전용 저장 경로**를
쓴다(공유 `output/vector_db` 가 아님) — `category.py` → `data/category`, `scenario.py` →
`data/scenario`. 임베딩 모델은 다른 유틸과 동일한 `BAAI/bge-m3`(`evaluation.category.vector_store`
재사용)라 컬렉션 간 자연어 검색 품질이 일관적이다.

**반드시 `python -m db.chromadb.import.<파일명>` 형태로 실행한다** — `import` 는 Python
예약어라 소스 코드에서 `from db.chromadb.import.category import ...` 처럼 점(.) 표기로 직접
임포트할 수 없다(`-m` 실행이나 `importlib` 문자열 임포트는 예약어 제약을 받지 않아 정상
동작한다). 이 폴더 안의 파일을 다른 모듈에서 재사용해야 한다면 폴더명을 바꿔야 한다.

```bash
python -m db.chromadb.import.category [--data_root output/total] [--db_path data/category] [--rebuild]
python -m db.chromadb.import.scenario [--data_root output/total] [--db_path data/scenario] [--rebuild]
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--data_root` | `output/total` | `<data_root>/<video_id>/*.json` 스캔 |
| `--db_path` | `data/category` \| `data/scenario` | ChromaDB 저장 경로 |
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

## MCP 서버 / Claude API 도구 — `chromadb-explorer`

`db.chromadb.*` 조회 유틸 4개(list_collections/show_schema/show_by_video_id/search_query)를
Claude CLI(`claude -p`/대화형 세션)와 Claude API 양쪽에 "도구"로 노출한다.
`evaluation/creative/mcp_server.py`(`creative-retrieval`)와 완전히 같은 패턴이다 —
[`../evaluation/creative/README.md`](../evaluation/creative/README.md)의 "MCP 서버" 절 참고.
`import/category.py`·`import/scenario.py`(컬렉션 삭제·재적재 배치 작업)는 도구로 올리지
않는다 — 사람이 CLI로 직접 실행한다.

| 도구 | 인자 | 반환 |
|------|------|------|
| `list_chromadb_collections` | 없음 | 저장소 3개(`output/vector_db`/`data/category`/`data/scenario`)를 모두 훑은 컬렉션·레코드 수·경로 |
| `show_chromadb_schema` | `collection`(필수), `sample_size`(기본 500) | 메타데이터 필드·타입·예시값 + 총 레코드 수 |
| `get_chromadb_record_by_video_id` | `collection`(필수), `video_id`(필수) | 해당 video_id 레코드 전체(원문, 유사도 없음) |
| `search_chromadb` | `collection`(필수), `query_text`(필수, 자연어), `n_results`(기본 5) | 유사도 상위 레코드 |

`db_path` 를 도구 인자로 받지 않는다 — `collection` 명만 주면 `tool_definitions._resolve_db_path`
가 알려진 3개 저장소를 훑어 자동으로 찾는다(호출하는 쪽이 내부 폴더 구조를 몰라도 됨). 컬렉션명이
겹치지 않는 한(현재는 겹치지 않음) 항상 정확히 찾는다.

**Claude CLI(MCP)**: 저장소 루트 `.mcp.json`에 `chromadb-explorer` 로 등록돼 있다.

```bash
python -m db.chromadb.mcp_server   # 로컬 실행/디버그
claude -p "..." --mcp-config .mcp.json --allowedTools "mcp__chromadb-explorer__search_chromadb"
```

`claude -p` 헤드리스 호출로 쓰려면 최초 1회 승인이 필요하다 — 로컬 `.claude/settings.json`
(개인 상태, `.gitignore` 로 제외)에 `{"enabledMcpjsonServers": ["chromadb-explorer"]}` 를 넣거나
프로젝트 디렉터리에서 `claude` 를 한 번 대화형으로 실행해 승인한다.

**Claude API(Anthropic tool_use)**: 로컬 stdio MCP 서버에 API 가 직접 붙을 수 없으므로(원격
HTTP/SSE MCP 커넥터만 지원), `db.chromadb.tool_definitions.TOOL_DEFINITIONS`(도구 스키마)와
`call_tool(name, arguments)`(디스패처)를 그대로 가져다 `messages.create(..., tools=...)` 호출과
tool_use 왕복 루프에 쓴다 — `generation/v5_m0_m3/llm_adapter.py::_chat_json_api_with_tools` 가
`evaluation.creative.reference_retrieval` 에 대해 하는 것과 같은 패턴이다.

**임베딩 모델 예열**: `mcp_server.py` 는 `__main__` 실행 시 `get_embedding_function()` 으로
bge-m3 를 서버 기동 시점에 미리 로드한다 — 그렇지 않으면 첫 `search_chromadb` 호출이 모델
로딩 비용까지 떠안아 느려지거나 타임아웃에 걸릴 수 있다.

## ChromaDB — `chromadb_search.py`

광고 카테고리 벡터 유사도 검색. 임베딩 모델은 `BAAI/bge-m3` (1024-dim, 한/영 cross-lingual).

```bash
python db/chromadb_search.py [--<벡터필드> 값 ...] [--<메타필터> 값 ...] [--n_results N]
```

### 벡터 유사도 텍스트 (입력값을 합쳐 쿼리 임베딩 생성)

`--industry_category`, `--product_category`, `--target_persona`, `--key_message`, `--usp`, `--positioning`, `--hook_strategy`, `--creative_style`, `--narrative_structure`, `--role_sequence`, `--key_scenes`, `--query` (자유 텍스트)

### 메타데이터 필터 (exact / range)

`--campaign_objective`, `--placement`, `--age_min`, `--age_max`, `--duration_max`

### 검색 제어

| 옵션 | 기본값 |
|------|--------|
| `--n_results` | 5 |
| `--db_path` | `output/vector_db` |
| `--collection` | `video_category` |
| `--json` | 결과를 JSON 으로 출력 |

### 예시

```bash
# 의류/신발 카테고리 유사 광고 5건
python db/chromadb_search.py --industry_category "의류" --product_category "신발" --n_results 5

# CTV 15초 광고 중 USP 의미가 유사한 광고
python db/chromadb_search.py --usp "초농밀 거품" --placement ctv_15s

# 자유 텍스트 쿼리 + 메타 필터
python db/chromadb_search.py --query "20~30대 남성을 위한 스킨케어" --age_min 20 --age_max 39
```

## ChromaDB — `chromadb_show.py`

컬렉션 내 모든 레코드를 덤프한다.

```bash
python db/chromadb_show.py
```

## ChromaDB — `chromadb_missing.py`

MySQL `video_uploads.id` 중 ChromaDB 컬렉션에 적재되지 않은 video_id 를 출력한다 (집합 차: DB − vector). 적재 누락분을 빠르게 찾을 때 사용한다.

```bash
python db/chromadb_missing.py [--db_path ...] [--collection ...] [--table video_uploads]
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--db_path` | `output/vector_db` | ChromaDB 저장 경로 |
| `--collection` | `video_category` | ChromaDB 컬렉션명 |
| `--table` | `video_uploads` | 비교 기준 MySQL 테이블명 |

## ChromaDB — `reembed.py`

`evaluation/category/vector_store.py::EMBEDDING_MODEL` 을 변경한 뒤 1회 실행하면 기존 컬렉션을 삭제하고 새 모델로 전체 재적재한다.

```bash
python db/reembed.py [--data_root <category_analysis 루트>] [--db_path ...] [--collection ...]
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--db_path` | `output/vector_db` | ChromaDB 저장 경로 |
| `--collection` | `video_category` | 컬렉션명 |
| `--data_root` | `../output/additional_0609/claude` | `<root>/<video_id>/category_analysis.json` 스캔 |

적재할 `category_analysis.json` 은 `python -m evaluation.cli --mode category --category_analysis` 로 먼저 생성한다 ([`../evaluation/category/README.md`](../evaluation/category/README.md) 참고).

## ChromaDB — `load_facets.py`

`<data_root>/<video_id>/concept_evaluation.json` 을 스캔해 facet 컬렉션 3개
(`ad_target`/`ad_usp`/`ad_creative`)에 일괄 적재한다. G1~G6 생성 파이프라인
([`../generation/README.md`](../generation/README.md)) 실행 전 1회 필요하다.

```bash
python db/load_facets.py [--data_root <concept_evaluation 루트>] [--db_path ...] [--rebuild]
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--db_path` | `output/vector_db` | ChromaDB 저장 경로 |
| `--data_root` | `output/total` | `<root>/<video_id>/concept_evaluation.json` 스캔 |
| `--rebuild` | off | 기존 facet 컬렉션 3개 삭제 후 재적재 |

## ChromaDB — `cluster.py`

컬렉션 내 임베딩을 K-Means 로 군집화한다. 광고 카탈로그가 자연스럽게 어떤 그룹으로 묶이는지 탐색할 때 사용한다.

```bash
python db/cluster.py [--k <정수|auto>] [--out <경로>] [옵션]
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--k` | `auto` | 클러스터 수. `auto` 는 silhouette score (cosine) 최대값으로 2..min(10, n//3) 범위에서 선택 |
| `--db_path` | `output/vector_db` | ChromaDB 저장 경로 |
| `--collection` | `video_category` | 컬렉션명 |
| `--out` | `output/vector_db_clusters.json` | 요약 JSON 저장 경로 |
| `--seed` | `42` | KMeans 재현용 시드 |

### 출력

콘솔에 클러스터별 우세 산업/제품·대표 멤버·전체 멤버 목록을 출력하고, 동일 내용을 JSON 으로 저장한다.

```json
{
  "k": 7,
  "n": 52,
  "silhouette_cosine": 0.1038,
  "clusters": [
    {
      "cluster_id": 5,
      "size": 10,
      "dominant_industries": [["food_beverage", 5], ["healthcare", 3], ["beauty", 1]],
      "dominant_products": [["탈모케어 샴푸", 1], ...],
      "representative": {"video_id": 351, "brand": "...", "document_head": "..."},
      "members": [{"video_id": 349, "brand": "...", "industry": "beauty", "product_category": "..."}]
    }
  ]
}
```

## `product_cliche_search.py` — 제품명 → 유사광고 검색 → 클리셰 비틀기 분석

제품명만 주면 (1) 웹검색으로 category/usp/target 프로필을 조사하고, (2) 그중 한 축으로
**creative vector db(`ad_production_reference`, record_kind=profile)** 를 검색해 유사 광고를
추출하고, (3) 그 결과를 하나의 임시 세그먼트로 보고 크리에이티브 요소 빈도를 집계해 클리셰를
비튼 광고와 포인트를 찾아 txt 로 저장한다. **`scenario_analysis.json`이나 `video_category`
(category DB)는 참조하지 않는다** — 이미 creative 요소가 적재된 영상만 검색 대상이라 자동
추출 단계가 없어 빠르지만, `ad_production_reference`에 없는 영상은 애초에 후보가 될 수
없다(먼저 `evaluation.cli --mode creative --extract --load_vector` 로 적재해둬야 검색 대상에
잡힌다).

```bash
python -m db.product_cliche_search --product_name "세스코" --retrieval_criteria usp
python -m db.product_cliche_search --product_name "제이에스티나" --retrieval_criteria category \
    --category "패션 주얼리·액세서리" --out output/cliche_twist/jestina_category.txt
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--product_name` | (필수) | 조사·검색할 제품/브랜드명 |
| `--category` / `--usp` / `--target` | — | 직접 지정하면 해당 항목은 웹검색 조사를 생략하고 그대로 사용 (셋 다 지정하면 리서치 자체를 건너뜀) |
| `--retrieval_criteria` | (필수) | `category`\|`usp`\|`target` — 유사도 검색에 쓸 축 1개 |
| `--n_results` | `15` | 추출할 광고 수 |
| `--duration_bucket` | `15s` | 대상 광고 길이 버킷 (`ad_production_reference`의 `duration_bucket` 필터) |
| `--db_path` | `output/vector_db` | ChromaDB 저장 경로 |
| `--out` | `output/cliche_twist/<제품명>_<기준>.txt` | 결과 저장 경로 |

### 동작 방식

1. **리서치**: `product_research.py` 가 `claude -p --allowedTools WebSearch` 로 실제 웹검색을 수행한다
   (`utils/llm_caller.py::call_claude` 의 `allowed_tools` 인자 — 헤드리스 `-p` 모드는 기본적으로
   WebSearch 권한을 거부하므로 명시적으로 허용해야 한다). `--category`/`--usp`/`--target` 을 지정한
   항목은 조사 결과 대신 그 값을 그대로 쓴다.
2. **검색**: `ad_retrieval.py` 가 지정 축 텍스트로 `ad_production_reference` 을 벌크 조회(oversample
   60건) 후 `duration_bucket == --duration_bucket` 로 필터링해 상위 N건을 추린다. 영상 1개 = 1레코드라
   video_id 자체로 이미 중복이 없다(단, 이 컬렉션엔 brand_name 메타데이터가 없어 리포트엔 제품
   카테고리 원문으로 영상을 식별한다).
3. **클리셰 집계**: `cliche_twist_analysis.py` 가 이 N건의 video_id 를 하나의 임시 세그먼트로 보고
   `fetch_elements`/`fetch_profiles`(`$in` 필터)로 이미 적재된 요소만 모아
   `evaluation/creative/cliche_aggregate.py::aggregate_elements` 로 빈도를 집계한다.
4. **비틀기 판정**: 세그먼트에 실제 `strong_cliche`/`convention`(빈도 ≥30%) 이 존재하는
   element_type 안에서, 혼자만 다른 subtype 을 쓴 `cliche_breaker` 만 "클리셰를 비튼 포인트"로
   인정한다. 대조군 없는 고립(모두 제각각이라 다수결 자체가 없는 경우)은 단순 다양성으로 보고 제외한다.
5. **리포트**: `cliche_twist_format.py` 가 광고 생성 LLM 이 그대로 참고할 수 있는 형태로 txt 를
   조립해 저장한다. 세그먼트 클리셰는 전부 나열하지 않고 `select_notable_cliches()` 로 추린다 —
   `strong_cliche`(빈도 60%↑)는 전부 포함하고, element_type 에 strong_cliche 가 없으면 가장
   우세한 `convention`(30~60%) 1건만 포함해 근소한 convention 여러 건이 나란히 나오는 잡음을
   줄인다. 각 항목에는 subtype 정의(`element_schema.py::describe_subtype`)와 실제 영상 예시
   발췌를 함께 적는다. 광고별 비틀기 포인트도 대조 subtype·이 광고의 subtype 정의를 함께 적는다.
