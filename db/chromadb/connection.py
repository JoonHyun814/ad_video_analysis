"""db/chromadb/ 전체가 공유하는 ChromaDB 클라이언트·컬렉션 연결 헬퍼 + 임베딩 함수.

EMBEDDING_MODEL/get_embedding_function 은 원래 evaluation/category/vector_store.py 가
소유했던 것을 여기로 흡수했다 — 이 저장소의 ChromaDB 접근은 이제 db/chromadb 하나로
통합되므로, 어떤 컬렉션을 적재/검색하든(video_category, category_analysis, scenario_analysis,
ad_concept_reference, ad_production_reference, ad_target/ad_usp/ad_creative) 이 한 곳의
임베딩 함수를 재사용한다.
"""
from __future__ import annotations

from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "output" / "vector_db"

EMBEDDING_MODEL = "BAAI/bge-m3"  # 한/영 cross-lingual 임베딩

_ef_cache: embedding_functions.SentenceTransformerEmbeddingFunction | None = None


def get_embedding_function() -> embedding_functions.SentenceTransformerEmbeddingFunction:
    """프로세스 단위로 임베딩 모델을 1회만 로드한다."""
    global _ef_cache
    if _ef_cache is None:
        _ef_cache = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
    return _ef_cache


def get_client(db_path: Path | str = DEFAULT_DB_PATH) -> chromadb.ClientAPI:
    """db_path 의 PersistentClient 를 연다."""
    return chromadb.PersistentClient(path=str(db_path))


def get_collection(client: chromadb.ClientAPI, name: str, with_embeddings: bool = False):
    """컬렉션을 가져온다.

    존재하지 않는 이름이면 ChromaDB 예외를 그대로 올린다 — 오타로 빈 컬렉션이 새로
    생기는 걸 막기 위해 get_or_create_collection 대신 get_collection 만 쓴다.
    with_embeddings=True 는 자연어 유사도 검색(query_texts)에 필요한 임베딩 함수를 붙인다 —
    get()/count() 만 쓸 때는 필요 없다.
    """
    if with_embeddings:
        return client.get_collection(name, embedding_function=get_embedding_function())
    return client.get_collection(name)


def get_or_create_collection(client: chromadb.ClientAPI, name: str, embedding_function=None):
    """적재 스크립트 전용 — 컬렉션이 있으면 가져오고, 없으면 cosine 유사도로 새로 만든다.

    embedding_function 을 안 주면 get_embedding_function() 을 기본으로 쓴다(이 저장소의
    모든 컬렉션이 같은 bge-m3 를 쓰므로).

    get_or_create_collection(metadata=...) 를 그대로 쓰면 기존 데이터가 초기화되는
    ChromaDB 1.5.x 버그가 있어 get/create 두 단계로 나눈다. 조회 전용 스크립트는 오타로
    빈 컬렉션이 새로 생기지 않도록 `get_collection` 만 쓰고, 이 함수는 적재(import) 스크립트만 쓴다.
    """
    ef = embedding_function if embedding_function is not None else get_embedding_function()
    try:
        return client.get_collection(name, embedding_function=ef)
    except Exception:
        return client.create_collection(name, embedding_function=ef, metadata={"hnsw:space": "cosine"})
