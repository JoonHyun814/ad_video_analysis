# evaluation/category

시나리오에서 광고 카테고리 메타데이터를 추출(`category_analysis.json`)하고
ChromaDB `video_category` 컬렉션에 적재한다.

## 파일 구성

| 파일 | 역할 |
|------|------|
| `run.py` | CLI 실행기 (`python -m evaluation.cli --mode category`) |
| `category_analysis.py` | 카테고리 추출 프롬프트 빌드 + claude 백엔드 구현 |
| `category_analysis_codex.py` / `_gemini.py` | 백엔드별 구현 |
| `vector_store.py` | `video_category` 컬렉션 upsert/query 헬퍼 + **임베딩 모델 정의** (`BAAI/bge-m3`, 1024-dim) |

`vector_store.py` 는 프로젝트 공용 임베딩 기반이기도 하다:
`db/`(chromadb_search·cluster·reembed·load_facets), `generation/g5_verification`,
`evaluation/concept` 의 벡터 스토어들이 여기의 `get_embedding_function`/`_get_or_create` 를 사용한다.
임베딩 모델 변경 시 `EMBEDDING_MODEL` 수정 후 `python db/reembed.py` 로 전체 재적재한다.

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
| `--db_path` | `output/vector_db` | ChromaDB 저장 경로 |
| `--collection` | `video_category` | 컬렉션명 |
| `--llm_backend` | `claude` | `claude` \| `codex` \| `gemini` |
| `--codex_model` / `--gemini_model` | — | 백엔드별 모델명 |

```bash
# 분석 + 적재 한 번에
python -m evaluation.cli --mode category --video_id 349 --category_analysis --load_vector \
    --data_dir output/additional_0609/claude
```

벡터 검색·클러스터링 사용법은 [`../../db/README.md`](../../db/README.md) 참고.
