# evaluation/category

시나리오에서 광고 카테고리 메타데이터를 추출(`category_analysis.json`)하고
ChromaDB `video_category` 컬렉션에 적재한다.

## 파일 구성

| 파일 | 역할 |
|------|------|
| `run.py` | CLI 실행기 (`python -m evaluation.cli --mode category`) — `--load_vector` 는 `db/chromadb/importers/video_category.py::upsert_video` 를 호출 |
| `category_analysis.py` | 카테고리 추출 프롬프트 빌드 + claude 백엔드 구현 |
| `category_analysis_codex.py` / `_gemini.py` | 백엔드별 구현 |

`video_category` 컬렉션 upsert/query 헬퍼와 임베딩 모델 정의(`BAAI/bge-m3`, 1024-dim)는
[`../../db/README.md`](../../db/README.md)의 `db/chromadb/connection.py`(임베딩 함수)·
`db/chromadb/importers/video_category.py`(upsert/query)로 이전됐다 — 이 저장소의 다른
컬렉션(`evaluation/concept`, `generation/g5_verification` 등)도 전부 같은 임베딩 함수를
공유한다. 임베딩 모델 변경 시 `db/chromadb/connection.py::EMBEDDING_MODEL` 수정 후
`db.chromadb.importers.video_category.upsert_batch` 로 전체 재적재한다.

## 실행

```bash
python -m evaluation.cli --mode category --video_id <ID> [--category_analysis] [--load_vector] [옵션]
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--video_id` | (필수) | 대상 영상 ID (int) |
| `--data_dir` | `output/product_plan/claude` | `<data_dir>/<video_id>/scenario_analysis.json` 입력 |
| `--category_analysis` | off | 카테고리 메타데이터 추출 → `category_analysis.json` |
| `--load_vector` | off | `category_analysis.json` 을 ChromaDB 에 upsert |
| `--db_path` | (미지정 시 자동) | ChromaDB 저장 경로 — 안 주면 `data/video_category/` 로 자동 결정된다 |
| `--collection` | `video_category` | 컬렉션명 |
| `--llm_backend` | `claude` | `claude` \| `codex` \| `gemini` |
| `--codex_model` / `--gemini_model` | — | 백엔드별 모델명 |

```bash
# 분석 + 적재 한 번에
python -m evaluation.cli --mode category --video_id 349 --category_analysis --load_vector \
    --data_dir output/additional_0609/claude
```

벡터 검색·클러스터링 사용법은 [`../../db/README.md`](../../db/README.md) 참고.
