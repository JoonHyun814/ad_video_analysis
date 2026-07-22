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
