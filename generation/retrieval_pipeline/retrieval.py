"""M5 — 장치별 검색을 실제로 실행한다(결정적, LLM 도구 호출이 아니라 순수 함수 호출).

device_scout.py 가 제안한 query_text/target_collection 을 그대로 evaluation/ad_concept_production
이 적재한 벡터 DB(output/vector_db 의 ad_concept_reference·ad_production_reference 컬렉션,
evaluation/creative/reference_retrieval.py 가 소유)에 쏜다. v5_m0_m3 의 --retrieval(M3/M4~M9)은
"검색할지·언제·몇 건" 을 LLM 이 tool_use 로 그때그때 판단하지만, 이 파이프라인은 반대로
**검색 실행 자체를 코드가 결정적으로 수행**한다 — 그래야 "서칭에 입력된 쿼리"와 "서칭 결과"를
LLM 응답과 무관하게 그대로 파일로 남길 수 있다(사용자 요청: 쿼리/검색결과/모델입력 투명성).
"""
from __future__ import annotations

from typing import Any

from evaluation.creative.reference_retrieval import (
    search_concept_reference,
    search_production_reference,
)
from generation.retrieval_pipeline.schemas import DeviceQuery

_DEFAULT_TOP_K = 3
_DEFAULT_ELEMENTS_PER_AD = 3


def _search_one(device: DeviceQuery, *, top_k: int, elements_per_ad: int, db_path: str) -> dict[str, Any]:
    collection = device.target_collection if device.target_collection == "concept" else "production"
    if collection == "concept":
        result = search_concept_reference(device.query_text, top_k=top_k, db_path=db_path)
    else:
        result = search_production_reference(
            device.query_text, top_k=top_k, elements_per_ad=elements_per_ad, db_path=db_path,
        )
    return {
        "device_name": device.name,
        "mechanism": device.mechanism,
        "collection": collection,
        "query_text": device.query_text,
        "top_k": top_k,
        "result_count": result.get("count", 0),
        "error": result.get("error"),
        "results": result.get("results", []),
    }


def run_searches(devices: list[DeviceQuery], *, top_k: int = _DEFAULT_TOP_K,
                 elements_per_ad: int = _DEFAULT_ELEMENTS_PER_AD,
                 db_path: str = "output/vector_db") -> list[dict[str, Any]]:
    """장치 후보마다 검색 1건씩 실행해 (쿼리+결과)를 묶어 반환한다 — 순서는 devices 순서 그대로."""
    return [_search_one(d, top_k=top_k, elements_per_ad=elements_per_ad, db_path=db_path) for d in devices]


def queries_only(searches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """"서칭에 입력되는 쿼리"만 뽑은 뷰 — 실제 검색 결과 없이 무엇을 물었는지만 기록."""
    return [
        {"device_name": s["device_name"], "collection": s["collection"],
         "query_text": s["query_text"], "top_k": s["top_k"]}
        for s in searches
    ]


def results_only(searches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """"서칭 결과로 나온 데이터"만 뽑은 뷰 — 어느 장치의 쿼리로 나온 결과인지 태그만 남기고 원문 그대로."""
    return [
        {"device_name": s["device_name"], "collection": s["collection"],
         "result_count": s["result_count"], "error": s["error"], "results": s["results"]}
        for s in searches
    ]
