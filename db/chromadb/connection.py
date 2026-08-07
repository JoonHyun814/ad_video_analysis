"""db/chromadb/ 스크립트가 공유하는 ChromaDB 클라이언트·컬렉션 연결 헬퍼."""
from __future__ import annotations

from pathlib import Path

import chromadb

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "output" / "vector_db"


def get_client(db_path: Path | str = DEFAULT_DB_PATH) -> chromadb.ClientAPI:
    """db_path 의 PersistentClient 를 연다."""
    return chromadb.PersistentClient(path=str(db_path))


def get_collection(client: chromadb.ClientAPI, name: str, with_embeddings: bool = False):
    """컬렉션을 가져온다.

    존재하지 않는 이름이면 ChromaDB 예외를 그대로 올린다 — 오타로 빈 컬렉션이 새로
    생기는 걸 막기 위해 get_or_create_collection 대신 get_collection 만 쓴다.
    with_embeddings=True 는 자연어 유사도 검색(query_texts)에 필요한 임베딩 함수
    (`BAAI/bge-m3`, `evaluation.category.vector_store` 재사용)를 붙인다 —
    get()/count() 만 쓸 때는 필요 없다.
    """
    if with_embeddings:
        from evaluation.category.vector_store import get_embedding_function
        return client.get_collection(name, embedding_function=get_embedding_function())
    return client.get_collection(name)


def get_or_create_collection(client: chromadb.ClientAPI, name: str, embedding_function=None):
    """적재 스크립트 전용 — 컬렉션이 있으면 가져오고, 없으면 cosine 유사도로 새로 만든다.

    get_or_create_collection(metadata=...) 를 그대로 쓰면 기존 데이터가 초기화되는
    ChromaDB 1.5.x 버그가 있어(`evaluation/category/vector_store.py::_get_or_create` 와
    동일 이유로) get/create 두 단계로 나눈다. 조회 전용 스크립트는 오타로 빈 컬렉션이
    새로 생기지 않도록 `get_collection` 만 쓰고, 이 함수는 적재(import) 스크립트만 쓴다.
    """
    try:
        return client.get_collection(name, embedding_function=embedding_function)
    except Exception:
        return client.create_collection(
            name, embedding_function=embedding_function, metadata={"hnsw:space": "cosine"}
        )
