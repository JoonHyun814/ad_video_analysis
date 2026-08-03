"""creative-retrieval MCP 서버 — ad_concept_reference/ad_production_reference 벡터 DB를
MCP 도구로 노출한다.

실제 검색 로직은 reference_retrieval.py 하나뿐이고, 이 파일은 그 함수를 FastMCP 도구로
등록하는 얇은 전송 계층이다(stdio). 등록은 저장소 루트 `.mcp.json` 이 담당 — 그 설정으로
`claude -p` 를 포함한 모든 Claude Code 세션이 이 서버를 자동 인식한다.

4개 도구를 모두 등록해두고, 실제로 어느 stage 가 어느 도구를 받을지는
generation/v5_m0_m3/llm_adapter.py 가 `--allowedTools` 로 매 호출마다 골라 좁힌다(M3=concept
계열, M4~M9/STORYBOARD_HTML=production 계열) — 이 서버 자체는 stage 를 모른다.

로컬 실행/디버그:
    python -m evaluation.creative.mcp_server
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from evaluation.creative.reference_retrieval import (
    list_concept_segment_columns as _list_concept_segment_columns,
)
from evaluation.creative.reference_retrieval import (
    list_production_segment_columns as _list_production_segment_columns,
)
from evaluation.creative.reference_retrieval import (
    search_concept_reference as _search_concept_reference,
)
from evaluation.creative.reference_retrieval import (
    search_production_reference as _search_production_reference,
)
from evaluation.creative.reference_retrieval import warm_up as _warm_up

mcp = FastMCP("creative-retrieval")


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
    # 임베딩 모델(bge-m3) 로딩을 서버 기동 시점에 미리 치른다 — 첫 검색 호출이 그 비용까지
    # 떠안아 claude -p 쪽 도구 호출 타임아웃에 걸리는 것을 피하기 위함(README 참고).
    _warm_up()
    mcp.run()
