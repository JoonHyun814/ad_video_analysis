"""chromadb-explorer MCP 서버 — db/chromadb 의 조회 유틸(list_collections/show_schema/
show_by_video_id/search_query)을 MCP 도구로 노출한다.

`evaluation/creative/mcp_server.py` 와 같은 얇은 FastMCP 전송 계층이다 — 실제 로직은
`db.chromadb.tool_definitions` 의 함수를 그대로 가져다 쓴다. 등록은 저장소 루트 `.mcp.json`
이 담당(`chromadb-explorer` 키) — 그 설정으로 `claude -p` 를 포함한 모든 Claude Code 세션이
이 서버를 자동 인식한다. Anthropic API 를 직접 호출하는 쪽은 이 서버 대신
`db.chromadb.tool_definitions.TOOL_DEFINITIONS`/`call_tool` 을 쓴다(로컬 stdio MCP 서버에
API 가 직접 붙을 수 없는 이유는 `generation/v5_m0_m3/llm_adapter.py` 모듈 docstring 참고).

`import/category.py`·`import/scenario.py`(컬렉션 삭제·재적재 배치 작업)는 도구로 올리지
않는다 — 사람이 CLI로 직접 실행한다.

로컬 실행/디버그:
    python -m db.chromadb.mcp_server
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from db.chromadb.tool_definitions import get_by_video_id as _get_by_video_id
from db.chromadb.tool_definitions import list_all_collections as _list_all_collections
from db.chromadb.tool_definitions import search as _search
from db.chromadb.tool_definitions import show_schema as _show_schema

mcp = FastMCP("chromadb-explorer")


@mcp.tool()
def list_chromadb_collections() -> dict:
    """이 프로젝트가 쓰는 ChromaDB 저장소(output/vector_db, data/category, data/scenario)를
    모두 훑어 컬렉션(테이블) 목록·레코드 수·저장 경로를 반환한다. 다른 chromadb 도구를 쓰기
    전에 어떤 컬렉션이 있는지 확인할 때 가장 먼저 호출하라.
    """
    return _list_all_collections()


@mcp.tool()
def show_chromadb_schema(collection: str, sample_size: int = 500) -> dict:
    """컬렉션 하나를 지정하면 메타데이터 필드·타입·예시값과 총 레코드 수를 반환한다.

    Args:
        collection: 조회할 컬렉션명(list_chromadb_collections 결과 참고).
        sample_size: 스키마 추론에 쓸 샘플 크기(기본 500).
    """
    return _show_schema(collection, sample_size=sample_size)


@mcp.tool()
def get_chromadb_record_by_video_id(collection: str, video_id: int) -> dict:
    """컬렉션 + video_id 를 지정하면 해당 video_id 의 레코드를 전부 반환한다(원문 확인용,
    유사도 검색이 아니다).

    Args:
        collection: 조회할 컬렉션명.
        video_id: 조회할 video_id.
    """
    return _get_by_video_id(collection, video_id)


@mcp.tool()
def search_chromadb(collection: str, query_text: str, n_results: int = 5) -> dict:
    """컬렉션 하나를 지정하고 자연어 쿼리로 유사도 검색한다(임베딩: BAAI/bge-m3, 한/영 모두
    잘 동작).

    Args:
        collection: 검색할 컬렉션명.
        query_text: 자연어 검색 쿼리(자유 서술 문장이 항상 안전).
        n_results: 반환 결과 수(기본 5).
    """
    return _search(collection, query_text, n_results=n_results)


if __name__ == "__main__":
    # 임베딩 모델(bge-m3) 로딩을 서버 기동 시점에 미리 치른다 — 첫 search_chromadb 호출이 그
    # 비용까지 떠안아 claude -p 쪽 도구 호출 타임아웃에 걸리는 것을 피하기 위함(evaluation/
    # creative/mcp_server.py 와 동일한 이유).
    from evaluation.category.vector_store import get_embedding_function
    get_embedding_function()
    mcp.run()
