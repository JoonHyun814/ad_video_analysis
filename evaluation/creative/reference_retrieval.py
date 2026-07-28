"""크리에이티브 벡터 DB(video_creative_profile/ad_creative_element)에서 참조 광고를 검색한다.

MCP 서버(mcp_server.py)와 generation/v5_m0_m3 의 Anthropic 툴콜 경로(llm_adapter.py) 양쪽이
이 모듈의 순수 함수를 그대로 호출한다 — 전송 계층(MCP stdio vs Anthropic tool_use)만 다르고
검색 로직은 하나다. db/ad_retrieval.py 와 달리 duration_bucket 외의 임의 세그먼트 컬럼으로
필터링할 수 있게 일반화했다.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import chromadb

from evaluation.category.vector_store import _get_or_create
from evaluation.creative import element_schema as es
from evaluation.creative.element_vector_store import ELEMENT_COLLECTION, PROFILE_COLLECTION, build_segment_where

_DEFAULT_DB = Path("output/vector_db")
_MAX_TOP_K = 20

# 호출 로깅(선택) — 환경변수로만 켜진다. 호출측(예: generation/v5_m0_m3)이 REFERENCE_RETRIEVAL_LOG_PATH
# 를 지정하면 도구 호출 1건마다 JSONL 로 append 한다. MCP(stdio 서브프로세스) 경유든 Anthropic
# tool_use(같은 프로세스) 경유든 이 두 환경변수만 셋업하면 동일하게 기록된다 — 로깅 로직을
# 전송 계층(mcp_server.py/llm_adapter.py)에 중복 구현하지 않기 위해 여기 한 곳에 둔다.
# REFERENCE_RETRIEVAL_LOG_STAGE 로 "어느 단계가 호출했는지"(예: "M1") 태그를 남길 수 있다.
_LOG_PATH_ENV = "REFERENCE_RETRIEVAL_LOG_PATH"
_LOG_STAGE_ENV = "REFERENCE_RETRIEVAL_LOG_STAGE"


def _log_call(tool: str, arguments: dict[str, Any], result: dict[str, Any]) -> None:
    log_path = os.environ.get(_LOG_PATH_ENV)
    if not log_path:
        return
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "stage": os.environ.get(_LOG_STAGE_ENV, ""),
        "tool": tool,
        "arguments": arguments,
        "result_count": result.get("count") if isinstance(result, dict) else None,
        "video_ids": [r.get("video_id") for r in result.get("results", [])] if isinstance(result, dict) else None,
        "segment_filter": result.get("segment_filter") if isinstance(result, dict) else None,
        "error": result.get("error") if isinstance(result, dict) else None,
    }
    try:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # 로깅 실패가 검색 자체를 막으면 안 됨

# chromadb.PersistentClient 캐시 — db_path 당 1개만 연다. MCP 서버(장수命 프로세스)에서
# search_reference_ads 가 매 호출마다 새 PersistentClient 를 열고(프로필 쿼리) 매칭된 영상 수만큼
# 추가로 또 열던(요소 조회, fetch_elements 루프) 구버전이 실측상 claude -p 경유 호출을 30분 넘게
# 멈추게 했다(같은 sqlite 파일에 대한 반복 PersistentClient 오픈이 원인으로 보임 — 직접 파이썬
# 호출/Anthropic API 툴콜 경로는 문제없이 빨랐다는 점과 대조됨). 클라이언트 재사용 + 요소 조회를
# 매칭 건별 N회 대신 단일 $in 쿼리로 합쳐 해결했다.
_clients: dict[str, "chromadb.ClientAPI"] = {}


def _client(db_path: str | Path):
    key = str(db_path)
    if key not in _clients:
        _clients[key] = chromadb.PersistentClient(path=key)
    return _clients[key]

# search_reference_ads 의 segment_column 으로 쓸 수 있는 컬럼과 허용 값 — element_schema.py 의
# enum 사전에서 파생해 항상 최신 상태를 유지한다(하드코딩 이중 관리 방지).
SEGMENT_COLUMNS: dict[str, tuple[str, ...]] = {
    "industry_category": es.INDUSTRY_CATEGORIES,
    "product_category_norm": tuple(sorted({v for vals in es.PRODUCT_CATEGORY_NORM.values() for v in vals})),
    "product_subtype": tuple(sorted({v for vals in es.PRODUCT_SUBTYPE.values() for v in vals})),
    "target_gender": es.TARGET_GENDER,
    "duration_bucket": es.DURATION_BUCKETS,
    "usp_category": es.USP_CATEGORY,
    "positioning_category": es.POSITIONING_CATEGORY,
    "price_tier": es.PRICE_TIER,
}


def warm_up(db_path: str | Path = _DEFAULT_DB) -> None:
    """임베딩 모델(bge-m3)을 미리 로드한다 — 첫 search_reference_ads 호출이 모델 로딩까지
    떠안아 느려지는 대신, MCP 서버 기동 시점에 그 비용을 미리 치른다(mcp_server.py 가 호출)."""
    client = _client(db_path)
    _get_or_create(client, PROFILE_COLLECTION)


_SEGMENT_VALUE_NOTE = (
    "이 값들은 evaluation/creative/element_schema.py 의 enum 사전에서 그대로 가져온 것이며 "
    "정확히 일치해야만 필터링된다(오타·유사어·의역 불가 — 예: 'home_appliance'는 되지만 "
    "'가전제품'·'homeappliance'는 안 된다). 특히 product_category_norm 처럼 '_norm' 이 붙은 "
    "컬럼은 표준화된 고정 enum 이라 반드시 이 목록에 있는 값 그대로만 써야 한다. 하고 싶은 "
    "필터링 의도에 정확히 맞는 값이 이 목록에 없으면 segment_column/segment_value 를 아예 "
    "생략하고 search_reference_ads 의 query_text(자연어 의미 검색)만으로 찾아라 — 비슷해 "
    "보이는 값을 추측해서 넣지 마라(결과 0건이 나올 수 있다)."
)


def list_segment_columns() -> dict[str, Any]:
    """search_reference_ads 의 segment_column/segment_value 로 쓸 수 있는 컬럼별 허용 값 목록."""
    out = {"columns": {col: list(vals) for col, vals in SEGMENT_COLUMNS.items()}, "note": _SEGMENT_VALUE_NOTE}
    _log_call("list_segment_columns", {}, {})
    return out


def search_reference_ads(
    query_text: str,
    segment_column: str | None = None,
    segment_value: str | None = None,
    top_k: int = 5,
    elements_per_ad: int = 4,
    db_path: str | Path = _DEFAULT_DB,
) -> dict[str, Any]:
    """query_text 의미 유사도로 참조 광고를 top_k 건 검색하고, 각 광고의 대표 크리에이티브
    요소(elements_per_ad 건)를 함께 반환한다.

    segment_column+segment_value 를 둘 다 주면 그 세그먼트로 먼저 필터링한 뒤 유사도 정렬한다.
    이 필터는 exact match 라 list_segment_columns() 가 준 값 그대로만 통한다 — 특히
    product_category_norm 같은 '_norm' 컬럼은 표준화된 enum 이므로 정확한 값이 아니면 결과가
    0건이 되거나(값 자체는 유효해도 그 세그먼트에 적재된 광고가 없을 수 있음) 거부된다.
    의도에 정확히 맞는 enum 값이 없으면 segment_column/segment_value 를 비우고 query_text 로만
    (자연어 의미 검색) 찾는 편이 낫다 — 비슷한 값을 추측해서 넣지 마라.
    """
    _args = {"query_text": query_text, "segment_column": segment_column,
              "segment_value": segment_value, "top_k": top_k}

    query_text = (query_text or "").strip()
    if not query_text:
        out = {"error": "query_text 는 필수입니다.", "results": []}
        _log_call("search_reference_ads", _args, out)
        return out
    top_k = max(1, min(int(top_k or 5), _MAX_TOP_K))

    where = None
    if segment_column and segment_value:
        if segment_column not in SEGMENT_COLUMNS:
            out = {
                "error": f"알 수 없는 segment_column: {segment_column!r}. "
                         f"list_segment_columns 로 유효한 컬럼을 확인하거나, 정확히 맞는 값이 "
                         f"없으면 segment_column/segment_value 를 생략하고 query_text 자연어 "
                         f"검색만 사용하세요.",
                "results": [],
            }
            _log_call("search_reference_ads", _args, out)
            return out
        if segment_value not in SEGMENT_COLUMNS[segment_column]:
            out = {
                "error": f"{segment_column!r} 에 허용되지 않는 값: {segment_value!r} — 이 "
                         f"필터는 exact match 라 list_segment_columns 가 준 값 그대로만 통합니다. "
                         f"정확히 맞는 값이 없으면 segment_column/segment_value 를 생략하고 "
                         f"query_text 자연어 검색만 사용하세요(비슷한 값을 추측해서 넣지 마세요).",
                "results": [],
            }
            _log_call("search_reference_ads", _args, out)
            return out
        where = build_segment_where(**{segment_column: segment_value})

    client = _client(db_path)
    col = _get_or_create(client, PROFILE_COLLECTION)
    if col.count() == 0:
        out = {"results": [], "count": 0, "note": "video_creative_profile 컬렉션이 비어 있습니다."}
        _log_call("search_reference_ads", _args, out)
        return out

    kwargs: dict[str, Any] = {
        "query_texts": [query_text],
        "n_results": min(top_k, col.count()),
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where
    res = col.query(**kwargs)

    matched = list(zip(res["documents"][0], res["metadatas"][0], res["distances"][0]))
    video_ids = [meta.get("video_id") for _, meta, _ in matched if meta.get("video_id") is not None]

    # 매칭된 영상 수만큼 반복 조회하지 않고 단일 $in 쿼리로 한 번에 가져온다(성능/안정성 — 위 주석 참고).
    elements_by_video: dict[Any, list[dict[str, Any]]] = {}
    if elements_per_ad > 0 and video_ids:
        elem_col = _get_or_create(client, ELEMENT_COLLECTION)
        elem_res = elem_col.get(where={"video_id": {"$in": video_ids}}, include=["documents", "metadatas"])
        for doc, meta in zip(elem_res["documents"], elem_res["metadatas"]):
            elements_by_video.setdefault(meta.get("video_id"), []).append({
                "type": meta.get("element_type"), "subtype": meta.get("element_subtype"), "description": doc,
            })

    results: list[dict[str, Any]] = []
    for doc, meta, dist in matched:
        video_id = meta.get("video_id")
        entry: dict[str, Any] = {
            "video_id": video_id,
            "similarity_distance": round(dist, 4),
            "industry_category": meta.get("industry_category"),
            "product_category_norm": meta.get("product_category_norm"),
            "product_category_raw": meta.get("product_category_raw"),
            "target_gender": meta.get("target_gender"),
            "usp_category": meta.get("usp_category"),
            "positioning_category": meta.get("positioning_category"),
            "price_tier": meta.get("price_tier"),
            "narrative_pattern": meta.get("narrative_pattern"),
            "summary": doc,
        }
        if elements_per_ad > 0:
            entry["notable_elements"] = elements_by_video.get(video_id, [])[:elements_per_ad]
        results.append(entry)

    out = {
        "results": results,
        "count": len(results),
        "segment_filter": {"column": segment_column, "value": segment_value} if where else None,
    }
    if where and not results:
        out["note"] = (
            f"{segment_column}={segment_value!r} 값 자체는 유효하지만 이 세그먼트에 적재된 "
            f"광고가 없습니다(enum 값 존재 ≠ 데이터 존재). segment_column/segment_value 를 "
            f"생략하고 query_text 만으로 다시 검색해 보세요."
        )
    _log_call("search_reference_ads", _args, out)
    return out


# ── 도구 정의(Anthropic tool_use 스키마) — MCP 서버와 API 백엔드 툴콜 경로가 공유하는 단일 소스 ──

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "list_segment_columns",
        "description": (
            "레퍼런스 광고 벡터 DB(video_creative_profile)에서 필터링 가능한 세그먼트 컬럼과 "
            "각 컬럼의 허용 값 목록을 반환한다(evaluation/creative/element_schema.py 의 enum 사전 "
            "그대로). search_reference_ads 에 segment_column/segment_value 를 넣기 **전에 반드시 "
            "먼저 호출**해서 정확한 값을 확인하라 — 특히 product_category_norm 처럼 '_norm' 이 "
            "붙은 컬럼은 표준화된 고정 enum 이라 이 목록에 있는 값 그대로만 통한다(오타·의역·추측 "
            "불가). 의도에 정확히 맞는 값이 없으면 segment_column/segment_value 를 쓰지 말고 "
            "search_reference_ads 의 query_text(자연어 의미 검색)만으로 찾아라."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "search_reference_ads",
        "description": (
            "제품/컨셉 설명(query_text)과 의미적으로 유사한 기존 참조 광고를 크리에이티브 벡터 "
            "DB에서 검색한다. query_text 는 자연어 자유 서술이라 항상 안전하다. 특정 산업/제품군/"
            "타겟성별/USP유형/포지셔닝/가격대로 먼저 좁히고 싶을 때만 segment_column + "
            "segment_value 를 함께 지정하되, 이 필터는 exact match 라 list_segment_columns 가 "
            "반환한 값과 정확히 같아야 한다 — 값이 유효해도 그 세그먼트에 적재된 광고가 없어 "
            "0건이 나올 수 있다. **정확히 맞는 enum 값이 없거나 확신이 없으면 segment_column/"
            "segment_value 를 아예 생략하고 query_text 만으로(자연어) 검색하라** — 비슷해 보이는 "
            "값을 추측해서 넣지 마라. top_k 로 몇 건을 가져올지 직접 정한다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query_text": {"type": "string", "description": "검색할 제품/컨셉/USP/타깃 등을 서술한 자연어 텍스트(항상 안전)"},
                "segment_column": {"type": "string", "enum": list(SEGMENT_COLUMNS.keys()),
                                    "description": "필터링할 세그먼트 컬럼명(선택, exact-match enum — list_segment_columns 로 먼저 값 확인 필수)"},
                "segment_value": {"type": "string",
                                   "description": "segment_column 의 정확한 enum 값(선택, list_segment_columns 가 준 값 그대로만 — 추측 금지)"},
                "top_k": {"type": "integer", "description": "가져올 참조 광고 개수(기본 5, 최대 20)", "default": 5},
            },
            "required": ["query_text"],
        },
    },
]


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """도구 이름 → 함수 디스패치(Anthropic tool_use 루프 전용, MCP 서버는 FastMCP 가 직접 라우팅)."""
    if name == "list_segment_columns":
        return list_segment_columns()
    if name == "search_reference_ads":
        return search_reference_ads(**arguments)
    return {"error": f"unknown tool: {name}"}
