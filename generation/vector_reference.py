"""M2 포지셔닝/M3 컨셉/M5 선정 컨셉으로 ChromaDB 에서 유사 광고를 조회·평가한다.

- M3: 포지셔닝과 유사한 기존 광고 N건을 참고 컨텍스트로 주입.
- M4: 컨셉별 top-1 매칭 거리 → threshold 초과 시 차별성 부족으로 강제 kill.
- M5: 선정 컨셉의 서사 필드(브랜드·산업 제외)로 유사 광고 N건을 참고 컨텍스트로 주입.
"""
import argparse
from pathlib import Path

from evaluation.vector_store import build_query_text, query as vector_query
from utils.io_checks import is_parse_failed


# ── 입력 → 쿼리 인자 매핑 ─────────────────────────────────────────────────────

def _m2_to_query_kwargs(brief: dict, m2: dict) -> dict:
    """브리프 + M2 포지셔닝을 vector_store.build_query_text 인자로 매핑한다."""
    inm = m2.get("inmarket_5pct") or {}
    non = m2.get("non_inmarket_95pct") or {}
    claims = inm.get("key_claims") or []
    dba = non.get("dba_assets") or []
    cep = non.get("cep_moments") or []
    return {
        "industry_category": brief.get("industry_category"),
        "product_category": brief.get("product_category"),
        "product": brief.get("product"),
        "target_persona": brief.get("target_persona"),
        "positioning": inm.get("dunford_differentiation") or brief.get("positioning"),
        "key_message": m2.get("dual_mandate") or brief.get("slogan"),
        "usp": ", ".join(claims) if claims else brief.get("usp"),
        "creative_style": ", ".join(cep) if cep else None,
        "key_scenes": ", ".join(dba) if dba else None,
    }


def _concept_to_query_kwargs(concept: dict) -> dict:
    """M3 컨셉 1개를 vector_store.build_query_text 인자로 매핑한다 (M4 유사도 검사용)."""
    tone = concept.get("tone")
    visual = concept.get("visual_language")
    creative = ", ".join(p for p in (tone, visual) if p) or None
    return {
        "hook_strategy": concept.get("hook"),
        "creative_style": creative,
        "key_message": concept.get("core_tension"),
        "narrative_structure": concept.get("narrative_structure"),
    }


def _narrative_only_kwargs(concept: dict) -> dict:
    """M5 서사 참고 전용 — '서사' 신호만 유지하고 메시지/포지셔닝 계열은 제외."""
    tone = concept.get("tone")
    visual = concept.get("visual_language")
    creative = ", ".join(p for p in (tone, visual) if p) or None
    return {
        "hook_strategy": concept.get("hook"),
        "creative_style": creative,
        "narrative_structure": concept.get("narrative_structure"),
    }


def _safe_query(text_kwargs: dict, n_results: int, db_path, collection) -> list[dict]:
    """build_query_text + vector_query 호출. 텍스트 부재·컬렉션 비어있음·예외 시 []."""
    text = build_query_text(**{k: v for k, v in text_kwargs.items() if v})
    if not text:
        return []
    try:
        return vector_query(text=text, n_results=n_results, db_path=db_path, collection_name=collection)
    except Exception as e:
        print(f"  [vector_reference] 유사도 조회 실패: {e}")
        return []


# ── 공개 API ──────────────────────────────────────────────────────────────────

def fetch_reference_ads(
    brief: dict,
    m2: dict,
    n_results: int = 5,
    db_path: str | Path = "output/vector_db",
    collection: str = "video_category",
) -> list[dict]:
    """M2 포지셔닝과 유사한 기존 광고 n_results 개를 반환한다."""
    return _safe_query(_m2_to_query_kwargs(brief, m2), n_results, db_path, collection)


def fetch_narrative_references(
    m3: dict,
    m4: dict,
    n_results: int = 5,
    db_path: str | Path = "output/vector_db",
    collection: str = "video_category",
) -> list[dict]:
    """선정 컨셉의 *서사 신호*만으로 유사 광고 n_results 개를 반환한다 (브랜드·산업·메시지 제외)."""
    from generation.m5_dr_script import _extract_concept  # m5 와 추출 로직 단일화
    concept = _extract_concept(m3, m4)
    if not concept:
        return []
    return _safe_query(_narrative_only_kwargs(concept), n_results, db_path, collection)


def evaluate_concept_similarity(
    m3: dict,
    threshold: float,
    db_path: str | Path = "output/vector_db",
    collection: str = "video_category",
) -> list[dict]:
    """컨셉별 top-1 매칭 광고·distance·threshold 초과 여부를 반환한다.

    cosine distance 는 작을수록 가까움. distance ≤ threshold → too_similar=True.
    """
    results: list[dict] = []
    for concept in m3.get("concepts") or []:
        cid = concept.get("id", "?")
        hits = _safe_query(_concept_to_query_kwargs(concept), 1, db_path, collection)
        if not hits:
            results.append({"id": cid, "top_match": None, "distance": None, "too_similar": False})
            continue
        top = hits[0]
        dist = float(top.get("distance") or 0.0)
        meta = top.get("metadata") or {}
        results.append({
            "id": cid,
            "top_match": {
                "video_id": meta.get("video_id"),
                "brand_name": meta.get("brand_name"),
                "industry_category": meta.get("industry_category"),
                "product_category": meta.get("product_category"),
            },
            "distance": dist,
            "too_similar": dist <= threshold,
        })
    return results


def enforce_similarity_kill(
    m4: dict,
    similarity_info: list[dict] | None,
    threshold: float | None,
) -> dict:
    """too_similar 컨셉이 selected 에 남았다면 killed 로 옮긴다. 잔여 0 이면 verdict 반송."""
    if not similarity_info or is_parse_failed(m4):
        return m4
    m4["similarity_check"] = {"threshold": threshold, "results": similarity_info}
    too_similar = {s["id"]: s for s in similarity_info if s.get("too_similar")}
    if not too_similar:
        return m4
    selected = [cid for cid in (m4.get("selected") or []) if cid not in too_similar]
    killed = list(m4.get("killed") or [])
    existing_ids = {k.get("id") for k in killed if isinstance(k, dict)}
    for cid, sim in too_similar.items():
        if cid in existing_ids:
            continue
        top = sim.get("top_match") or {}
        killed.append({
            "id": cid,
            "reason": (
                f"기존 광고 video_id={top.get('video_id')} 와 cosine distance "
                f"{sim.get('distance'):.4f} (threshold {threshold:.2f}) → 차별성 부족 강제 kill"
            ),
        })
    m4["selected"] = selected
    m4["killed"] = killed
    if not selected:
        m4["verdict"] = "return_to_phase1"
        prev = m4.get("return_reason") or ""
        m4["return_reason"] = (prev + " | " if prev else "") + "유사도 강제 kill 로 잔여 컨셉 없음"
    return m4


# ── 파이프라인 진입점용 어댑터 ─────────────────────────────────────────────────

def maybe_reference_ads(args: argparse.Namespace, brief: dict, m2: dict) -> list[dict] | None:
    """--m3_reference 플래그가 켜져 있을 때만 유사 광고를 조회해 반환한다."""
    if not getattr(args, "m3_reference", False):
        return None
    refs = fetch_reference_ads(
        brief, m2,
        n_results=args.m3_reference_n,
        db_path=args.vector_db_path,
        collection=args.vector_collection,
    )
    print(f"  [M3] 유사 광고 {len(refs)}건 참고")
    return refs


def maybe_similarity_info(
    args: argparse.Namespace, m3: dict,
) -> tuple[list[dict] | None, float | None]:
    """--m4_similarity_kill 플래그가 켜져 있을 때만 컨셉별 유사도 검사를 수행한다."""
    if not getattr(args, "m4_similarity_kill", False):
        return None, None
    threshold = args.m4_similarity_threshold
    info = evaluate_concept_similarity(
        m3, threshold=threshold,
        db_path=args.vector_db_path,
        collection=args.vector_collection,
    )
    kills = sum(1 for s in info if s.get("too_similar"))
    print(f"  [M4] 유사도 검사: {len(info)}건 중 {kills}건이 threshold(≤{threshold}) 초과")
    return info, threshold


def maybe_narrative_references(
    args: argparse.Namespace, m3: dict, m4: dict,
) -> list[dict] | None:
    """--m5_narrative_reference 플래그가 켜져 있을 때만 서사 유사 광고를 조회한다."""
    if not getattr(args, "m5_narrative_reference", False):
        return None
    refs = fetch_narrative_references(
        m3, m4,
        n_results=args.m5_narrative_reference_n,
        db_path=args.vector_db_path,
        collection=args.vector_collection,
    )
    print(f"  [M5] 서사 유사 광고 {len(refs)}건 참고")
    return refs
