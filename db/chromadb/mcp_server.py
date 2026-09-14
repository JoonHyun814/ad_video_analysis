"""chromadb-explorer MCP 서버 — `search_chromadb` 도구 하나만 노출하는 stdio MCP 서버.

이 저장소의 유일한 ChromaDB MCP 서버다. 실제 로직은 `db.chromadb.tool_definitions.search_chromadb`
를 그대로 가져다 쓴다 — 이 파일은 얇은 FastMCP 전송 계층일 뿐이다. 등록은 저장소 루트
`.mcp.json`이 담당(`chromadb-explorer` 키) — 그 설정으로 `claude -p` 를 포함한 모든 Claude
Code 세션이 이 서버를 자동 인식한다. Anthropic API 를 직접 호출하는 쪽은 이 서버 대신
`db.chromadb.tool_definitions.TOOL_DEFINITIONS`/`call_tool` 을 쓴다(로컬 stdio MCP 서버에
API 가 직접 붙을 수 없는 이유는 `generation/v5_m0_m3/llm_adapter.py` 모듈 docstring 참고).

호출마다 `<log_prefix>.jsonl` 에 로그가 남는다(기본 위치 `logs/search_chromadb/<날짜>/`, 호출측이
`SEARCH_CHROMADB_LOG_DIR` 환경변수로 재지정 가능 — `tool_definitions.py` 참고).
`list_collections`/`show_schema`/`show_by_video_id`/`importers/*`(컬렉션 조회·삭제·재적재)는
도구로 올리지 않는다 — 사람이 CLI로 직접 실행한다.

로컬 실행/디버그:
    python -m db.chromadb.mcp_server
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from db.chromadb.tool_definitions import fetch_by_video_id as _fetch_by_video_id
from db.chromadb.tool_definitions import search_chromadb as _search_chromadb
from db.chromadb.tool_definitions import search_chromadb_hybrid as _search_chromadb_hybrid

mcp = FastMCP("chromadb-explorer")


@mcp.tool()
def search_chromadb(collection: str, query_text: str, n_results: int = 5, log_prefix: str = "default") -> dict:
    """컬렉션 하나를 지정하고 자연어 쿼리로 유사도 검색한다(임베딩: BAAI/bge-m3, 한/영 모두
    잘 동작). 호출마다 <log_prefix>.jsonl 에 기록된다(기본 위치 logs/search_chromadb/<날짜>/).
    브랜드명·숫자·특정 용어처럼 정확히 일치해야 하는 키워드가 있다면 search_chromadb_hybrid 를
    대신 써라.

    Args:
        collection: 검색할 컬렉션명(예: ad_concept_reference, ad_production_reference,
            category_analysis, scenario_analysis, video_category).
        query_text: 자연어 검색 쿼리(자유 서술 문장이 항상 안전).
        n_results: 반환 결과 수(기본 5).
        log_prefix: 호출 로그 파일명(<log_prefix>.jsonl) — 이 호출이 어떤 맥락(프로젝트/단계명
            등)에서 나왔는지 표시한다. 미지정 시 'default'.
    """
    return _search_chromadb(collection, query_text, n_results, log_prefix)


@mcp.tool()
def search_chromadb_hybrid(collection: str, query_text: str, n_results: int = 5, log_prefix: str = "default") -> dict:
    """search_chromadb 와 동일한 컬렉션을 dense 유사도 + BM25 키워드 검색을 RRF 로 결합해 찾는다.
    브랜드명·숫자·특정 용어처럼 정확히 그 단어가 포함돼야 의미 있는 쿼리일 때 search_chromadb
    보다 이 도구를 우선 써라. 호출마다 <log_prefix>.jsonl 에 기록된다(기본 위치
    logs/search_chromadb/<날짜>/).

    Args:
        collection: 검색할 컬렉션명(예: ad_concept_reference, ad_production_reference,
            category_analysis, scenario_analysis, video_category).
        query_text: 자연어 검색 쿼리(브랜드명·숫자 등 정확 매칭 키워드 포함 가능).
        n_results: 반환 결과 수(기본 5).
        log_prefix: 호출 로그 파일명(<log_prefix>.jsonl) — 이 호출이 어떤 맥락(프로젝트/단계명
            등)에서 나왔는지 표시한다. 미지정 시 'default'.
    """
    return _search_chromadb_hybrid(collection, query_text, n_results, log_prefix)


@mcp.tool()
def fetch_by_video_id(collection: str, video_id: int, log_prefix: str = "default") -> dict:
    """search_chromadb(_hybrid) 로 특정 광고(video_id)를 이미 찾은 뒤, 요약이 아니라 원본
    레코드 전체가 필요할 때 쓴다 — 탐색·발견 목적으로는 쓰지 마라(검색 도구의 역할). 호출마다
    <log_prefix>.jsonl 에 기록된다(기본 위치 logs/search_chromadb/<날짜>/).

    Args:
        collection: 조회할 컬렉션명.
        video_id: 조회할 광고의 video_id(검색 도구 결과의 metadata.video_id).
        log_prefix: 호출 로그 파일명(<log_prefix>.jsonl) — 이 호출이 어떤 맥락(프로젝트/단계명
            등)에서 나왔는지 표시한다. 미지정 시 'default'.
    """
    return _fetch_by_video_id(collection, video_id, log_prefix)


if __name__ == "__main__":
    # 임베딩 모델(bge-m3) 로딩을 서버 기동 시점에 미리 치른다 — 첫 search_chromadb 호출이 그
    # 비용까지 떠안아 claude -p 쪽 도구 호출이 타임아웃에 걸리는 것을 피하기 위함. search_chromadb
    # 는 임의의 컬렉션을 검색하므로 특정 컬렉션이 아니라 임베딩 함수 자체만 예열한다.
    from db.chromadb.connection import get_embedding_function
    get_embedding_function()
    mcp.run()
