"""새 컨셉 파이프라인 CM3 — 4개 관점으로 video_concept 컬렉션에서 참고 광고를 수집한다.

전략 유사(같은 카테고리) / 타겟·USP·포지셔닝 유사 는 임베딩 유사도로,
소구 유형 다각화 / 연출 스타일 다각화 는 category 값이 서로 다른 광고를 표본 추출한다 — 렌즈마다 조회 방식이 다르다.
"""
from pathlib import Path

from evaluation.concept_vector_store import (
    APPEAL_TYPE_CHOICES,
    EXECUTION_STYLE_CHOICES,
    build_query_text,
    query_similar,
    sample_by_category,
)

_LENS_LABELS = {
    "similar_strategy": "비슷한 제품의 광고 전략",
    "similar_target": "비슷한 타겟·USP·포지셔닝",
    "diverse_appeal": "소구 유형(appeal_type)이 서로 다른 광고 — 창의적 다각화 참고",
    "diverse_execution": "연출 스타일(execution_style)이 서로 다른 광고 — 표현 다각화 참고",
}


def _safe(fn) -> list[dict]:
    """컬렉션이 비었거나 조회 실패 시 빈 리스트로 대체한다 (파이프라인은 계속 진행)."""
    try:
        return fn()
    except Exception as e:
        print(f"  [m3_reference_collection] 조회 실패: {e}")
        return []


def _dedupe(rows: list[dict]) -> list[dict]:
    """video_id 기준 중복을 제거한다 (여러 렌즈에 동시에 잡힐 수 있음)."""
    seen: set = set()
    out: list[dict] = []
    for r in rows:
        vid = (r.get("metadata") or {}).get("video_id")
        if vid in seen:
            continue
        seen.add(vid)
        out.append(r)
    return out


def collect_references(
    cm1: dict,
    cm2: dict,
    n_per_lens: int = 5,
    db_path: str | Path = "output/vector_db",
    collection: str = "video_concept",
) -> dict:
    """CM1/CM2 결과로 4개 렌즈에서 참고 광고를 수집한다. 컬렉션이 비어있으면 빈 리스트로 채운다."""
    industry = cm1.get("industry_category")
    where = {"industry_category": {"$eq": industry}} if industry else None
    strategy_text = build_query_text(industry_category=industry, product_category=cm1.get("product_category"))
    target_text = build_query_text(
        target_persona=cm2.get("target_persona"), usp=cm2.get("usp"), positioning=cm2.get("positioning"),
    )
    kw = dict(db_path=db_path, collection_name=collection)

    lenses = {
        "similar_strategy": _safe(lambda: query_similar(strategy_text, n_results=n_per_lens, where=where, **kw)) if strategy_text else [],
        "similar_target": _safe(lambda: query_similar(target_text, n_results=n_per_lens, **kw)) if target_text else [],
        "diverse_appeal": _safe(lambda: sample_by_category("appeal_type", APPEAL_TYPE_CHOICES, n_results=n_per_lens, **kw)),
        "diverse_execution": _safe(lambda: sample_by_category("execution_style", EXECUTION_STYLE_CHOICES, n_results=n_per_lens, **kw)),
    }
    return {
        "lens_labels": _LENS_LABELS,
        "lenses": lenses,
        "all": _dedupe([r for rows in lenses.values() for r in rows]),
    }
