"""chromadb-explorer MCP 서버 — db/chromadb 의 조회 유틸(list_collections/show_schema/
show_by_video_id/search_query) + 참조 광고 검색(creative_search)을 MCP 도구로 노출한다.

이 저장소의 유일한 ChromaDB MCP 서버다 — 예전에 별도로 있던 `evaluation/creative/
mcp_server.py`(`creative-retrieval`)는 여기로 흡수됐다(도구 4개 그대로: list/search ×
concept/production). 실제 로직은 `db.chromadb.tool_definitions`(범용 조회)와
`db.chromadb.creative_search`(참조 광고 검색)의 함수를 그대로 가져다 쓴다 — 이 파일은 얇은
FastMCP 전송 계층일 뿐이다. 등록은 저장소 루트 `.mcp.json`이 담당(`chromadb-explorer` 키) —
그 설정으로 `claude -p` 를 포함한 모든 Claude Code 세션이 이 서버를 자동 인식한다.
Anthropic API 를 직접 호출하는 쪽은 이 서버 대신 `db.chromadb.tool_definitions.TOOL_DEFINITIONS`/
`call_tool` 이나 `db.chromadb.creative_search.TOOL_DEFINITIONS_*`/`call_tool` 을 쓴다(로컬
stdio MCP 서버에 API 가 직접 붙을 수 없는 이유는 `generation/v5_m0_m3/llm_adapter.py` 모듈
docstring 참고).

`importers/category.py`·`importers/scenario.py`(컬렉션 삭제·재적재 배치 작업)는 도구로
올리지 않는다 — 사람이 CLI로 직접 실행한다.

로컬 실행/디버그:
    python -m db.chromadb.mcp_server
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from db.chromadb.creative_search import list_concept_segment_columns as _list_concept_segment_columns
from db.chromadb.creative_search import list_production_segment_columns as _list_production_segment_columns
from db.chromadb.creative_search import search_concept_reference as _search_concept_reference
from db.chromadb.creative_search import search_production_reference as _search_production_reference
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


@mcp.tool()
def list_concept_segment_columns() -> dict:
    """전략 레퍼런스 광고 벡터 DB(ad_concept_reference)에서 필터링 가능한 세그먼트 컬럼과 각
    컬럼의 허용 값 목록을 반환한다(evaluation/creative/element_schema.py 의 enum 사전 그대로).

    search_concept_reference 에 segment_column/segment_value 를 넣기 **전에 반드시 먼저 호출**
    해서 정확한 값을 확인하라(오타·의역·추측 불가). 의도에 정확히 맞는 값이 없으면
    segment_column/segment_value 를 쓰지 말고 search_concept_reference 의 query_text(자연어
    의미 검색)만으로 찾아라.
    """
    return _list_concept_segment_columns()


@mcp.tool()
def search_concept_reference(
    query_text: str,
    segment_column: str = "",
    segment_value: str = "",
    top_k: int = 5,
) -> dict:
    """이 제품/브리프와 전략적으로 비슷한 기존 광고(소구·포지셔닝·타겟)를 검색한다.

    Args:
        query_text: 검색할 제품/타깃/USP/포지셔닝 등을 서술한 자연어 텍스트(필수, 항상 안전).
        segment_column: 필터링할 세그먼트 컬럼명(선택, exact-match enum). list_concept_segment_columns
            로 먼저 값을 확인해야 한다.
        segment_value: segment_column 의 정확한 enum 값(선택, 추측 금지). 정확히 맞는 값이
            없으면 segment_column/segment_value 를 아예 생략하고 query_text 만으로 검색하라.
        top_k: 가져올 참조 광고 개수(기본 5, 최대 20).
    """
    return _search_concept_reference(
        query_text,
        segment_column=segment_column or None,
        segment_value=segment_value or None,
        top_k=top_k,
    )


@mcp.tool()
def list_production_segment_columns() -> dict:
    """연출 레퍼런스 광고 벡터 DB(ad_production_reference)에서 필터링 가능한 세그먼트 컬럼과
    각 컬럼의 허용 값 목록을 반환한다(evaluation/creative/element_schema.py 의 enum 사전 그대로).

    search_production_reference 에 segment_column/segment_value 를 넣기 **전에 반드시 먼저
    호출**해서 정확한 값을 확인하라 — 특히 product_category_norm 처럼 '_norm' 이 붙은 컬럼은
    표준화된 고정 enum 이라 이 목록에 있는 값 그대로만 통한다(오타·의역·추측 불가). 의도에
    정확히 맞는 값이 없으면 segment_column/segment_value 를 쓰지 말고
    search_production_reference 의 query_text(자연어 의미 검색)만으로 찾아라.
    """
    return _list_production_segment_columns()


@mcp.tool()
def search_production_reference(
    query_text: str,
    segment_column: str = "",
    segment_value: str = "",
    top_k: int = 5,
) -> dict:
    """컨셉·스크립트와 비슷하게 연출된 기존 광고와 대표 크리에이티브 요소를 검색한다.

    query_text 는 자연어 자유 서술이라 항상 안전하다. segment_column/segment_value 는 exact
    match 필터라 list_production_segment_columns 가 반환한 값과 정확히 같아야 한다 — 값이
    유효해도 그 세그먼트에 적재된 광고가 없어 0건이 나올 수 있다.

    Args:
        query_text: 검색할 연출·톤·서사·기법 등을 서술한 자연어 텍스트(필수, 항상 안전).
        segment_column: 필터링할 세그먼트 컬럼명(선택, exact-match enum). list_production_segment_columns
            로 먼저 값을 확인해야 한다.
        segment_value: segment_column 의 정확한 enum 값(선택, 추측 금지). 정확히 맞는 값이
            없으면 segment_column/segment_value 를 아예 생략하고 query_text 만으로(자연어)
            검색하라.
        top_k: 가져올 참조 광고 개수(기본 5, 최대 20) — 몇 건이 적절할지는 호출하는 쪽이 판단한다.
    """
    return _search_production_reference(
        query_text,
        segment_column=segment_column or None,
        segment_value=segment_value or None,
        top_k=top_k,
    )


if __name__ == "__main__":
    # 임베딩 모델(bge-m3) 로딩을 서버 기동 시점에 미리 치른다 — 첫 search_chromadb/
    # search_production_reference 호출이 그 비용까지 떠안아 claude -p 쪽 도구 호출이
    # 타임아웃에 걸리는 것을 피하기 위함. ad_concept_reference/ad_production_reference
    # 컬렉션도 함께 예열한다(creative_search.warm_up).
    from db.chromadb.creative_search import warm_up
    warm_up()
    mcp.run()
