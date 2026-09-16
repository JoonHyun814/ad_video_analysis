"""Kùzu(임베디드 그래프 DB) 연결 헬퍼 — 단일 그래프(`data/ad_graph/`)만 쓴다.

컬렉션별로 나뉘는 ChromaDB와 달리 이 그래프는 전체 캠페인을 아우르는 하나의 그래프라
`db_path_for()`(db.chromadb.connection 재사용)로 `data/` 루트 아래 경로만 얻어 쓴다.
"""
from __future__ import annotations

import kuzu

from db.chromadb.connection import db_path_for

GRAPH_NAME = "ad_graph"
DB_PATH = db_path_for(GRAPH_NAME)

_db_cache: kuzu.Database | None = None
_conn_cache: kuzu.Connection | None = None


def get_connection() -> kuzu.Connection:
    """프로세스 단위로 Kùzu 연결을 1회만 연다."""
    global _db_cache, _conn_cache
    if _conn_cache is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _db_cache = kuzu.Database(str(DB_PATH))
        _conn_cache = kuzu.Connection(_db_cache)
    return _conn_cache
