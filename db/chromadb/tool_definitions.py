"""db/chromadb 조회 유틸(list_collections/show_schema/show_by_video_id/search_query)을
Claude CLI(MCP, `mcp_server.py`)와 Claude API(Anthropic 네이티브 tool_use) 양쪽에 노출하는
공유 스키마 + 디스패처.

`evaluation/creative/reference_retrieval.py` 의 `TOOL_DEFINITIONS_*`/`call_tool` 과 같은
역할이다 — 검색 로직은 각 CLI 스크립트에 그대로 두고, 두 전송 경로(MCP stdio / Anthropic
tool_use)가 이 파일의 스키마와 디스패처를 공유한다. `import/category.py`·`import/scenario.py`
(컬렉션을 지우고 재적재하는 배치 작업)는 도구로 올리지 않는다 — 사람이 CLI로 직접 실행한다.

이 프로젝트는 컬렉션이 물리적으로 3개 저장소에 나뉘어 있어(`output/vector_db`,
`data/category`, `data/scenario`), `db_path` 를 안 주면 컬렉션명으로 자동으로 저장소를
찾는다(`_resolve_db_path`) — 호출하는 쪽(에이전트)이 내부 폴더 구조를 몰라도 된다.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from db.chromadb.connection import DEFAULT_DB_PATH, get_client
from db.chromadb.list_collections import list_collections as _list_collections
from db.chromadb.search_query import search as _search_impl
from db.chromadb.show_by_video_id import fetch_by_video_id as _fetch_by_video_id
from db.chromadb.show_schema import inspect_schema as _inspect_schema

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_KNOWN_STORES: list[Path] = [
    DEFAULT_DB_PATH,                        # video_category, ad_production_reference, ad_concept_reference
    _PROJECT_ROOT / "data" / "category",    # category_analysis
    _PROJECT_ROOT / "data" / "scenario",    # scenario_analysis
]


def _resolve_db_path(collection: str, db_path: str) -> Path:
    """db_path 를 명시하지 않으면 알려진 저장소 중 해당 컬렉션이 있는 곳을 찾는다."""
    if db_path:
        return Path(db_path)
    for store in _KNOWN_STORES:
        if not store.exists():
            continue
        try:
            names = {c.name for c in get_client(store).list_collections()}
        except Exception:
            continue
        if collection in names:
            return store
    return DEFAULT_DB_PATH


def list_all_collections() -> dict[str, Any]:
    """알려진 저장소를 모두 훑어 컬렉션 목록 + 레코드 수 + 저장 경로를 반환한다."""
    rows = [
        {"collection": name, "count": count, "db_path": str(store)}
        for store in _KNOWN_STORES if store.exists()
        for name, count in _list_collections(store)
    ]
    return {"stores": [str(s) for s in _KNOWN_STORES], "collections": rows}


def show_schema(collection: str, db_path: str = "", sample_size: int = 500) -> dict[str, Any]:
    """컬렉션 하나의 메타데이터 스키마(필드·타입·예시)와 데이터 수를 반환한다."""
    return _inspect_schema(collection, _resolve_db_path(collection, db_path), sample_size)


def get_by_video_id(collection: str, video_id: int, db_path: str = "") -> dict[str, Any]:
    """컬렉션 + video_id 로 해당 레코드를 전부 반환한다."""
    records = _fetch_by_video_id(collection, video_id, _resolve_db_path(collection, db_path))
    return {"collection": collection, "video_id": video_id, "count": len(records), "records": records}


def search(collection: str, query_text: str, n_results: int = 5, db_path: str = "") -> dict[str, Any]:
    """자연어 쿼리로 컬렉션을 유사도 검색한다."""
    results = _search_impl(collection, query_text, n_results, _resolve_db_path(collection, db_path))
    return {"collection": collection, "query_text": query_text, "count": len(results), "results": results}


# ── 도구 정의(Anthropic tool_use 스키마) — MCP 서버와 API 백엔드 툴콜 경로가 공유하는 단일 소스 ──

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "list_chromadb_collections",
        "description": (
            "이 프로젝트가 쓰는 ChromaDB 저장소(output/vector_db, data/category, data/scenario)를 "
            "모두 훑어 컬렉션(테이블) 목록·레코드 수·저장 경로를 반환한다. 다른 chromadb 도구를 "
            "쓰기 전에 어떤 컬렉션이 있는지 확인할 때 가장 먼저 호출하라."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "show_chromadb_schema",
        "description": (
            "컬렉션 하나를 지정하면 메타데이터 필드·타입·예시값과 총 레코드 수를 반환한다. "
            "ChromaDB 는 고정 스키마가 없어 샘플 레코드에서 필드를 추론한다 — 어떤 필드로 "
            "검색·필터링할 수 있는지 확인할 때 쓴다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "collection": {"type": "string", "description": "조회할 컬렉션명(list_chromadb_collections 결과 참고)"},
                "sample_size": {"type": "integer", "description": "스키마 추론에 쓸 샘플 크기(기본 500)", "default": 500},
            },
            "required": ["collection"],
        },
    },
    {
        "name": "get_chromadb_record_by_video_id",
        "description": "컬렉션 + video_id 를 지정하면 해당 video_id 의 레코드를 전부 반환한다(원문 확인용, 유사도 검색 아님).",
        "input_schema": {
            "type": "object",
            "properties": {
                "collection": {"type": "string", "description": "조회할 컬렉션명"},
                "video_id": {"type": "integer", "description": "조회할 video_id"},
            },
            "required": ["collection", "video_id"],
        },
    },
    {
        "name": "search_chromadb",
        "description": (
            "컬렉션 하나를 지정하고 자연어 쿼리로 유사도 검색한다(임베딩: BAAI/bge-m3, 한/영 "
            "모두 잘 동작). query_text 는 자유 서술 문장이 항상 안전하다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "collection": {"type": "string", "description": "검색할 컬렉션명"},
                "query_text": {"type": "string", "description": "자연어 검색 쿼리"},
                "n_results": {"type": "integer", "description": "반환 결과 수(기본 5)", "default": 5},
            },
            "required": ["collection", "query_text"],
        },
    },
]


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """도구 이름 → 함수 디스패치(Anthropic tool_use 루프 전용, MCP 서버는 FastMCP 가 직접 라우팅)."""
    if name == "list_chromadb_collections":
        return list_all_collections()
    if name == "show_chromadb_schema":
        return show_schema(arguments["collection"], sample_size=arguments.get("sample_size", 500))
    if name == "get_chromadb_record_by_video_id":
        return get_by_video_id(arguments["collection"], arguments["video_id"])
    if name == "search_chromadb":
        return search(arguments["collection"], arguments["query_text"], arguments.get("n_results", 5))
    return {"error": f"unknown tool: {name}"}
