"""광고주가 지정한 장르·산업·타겟·USP 로 클리셰 분석 대상 세그먼트를 추출한다 (G2 전반부, LLM 미사용).

exact 필터(장르+산업)로 시작해 세그먼트가 작으면 산업 → 장르 → 전체 순으로 계층 완화하고,
타겟/USP facet 임베딩 유사도를 RRF 로 병합해 상위 멤버를 랭킹한다.
결과에 완화 수준(relax_level)과 후보 수를 남겨 분포 판단의 신뢰 근거로 쓴다.
"""
from pathlib import Path

from db.chromadb.importers.facets import fetch_members, query_facet

_RELAX_LEVELS: tuple[tuple[str, bool, bool], ...] = (
    ("genre+industry", True, True),
    ("industry", False, True),
    ("genre", True, False),
    ("global", False, False),
)
_RRF_K = 60
_FACET_WEIGHTS = {"target": 0.5, "usp": 0.5}


def _build_where(use_genre: bool, use_industry: bool, genre: str, industry: str) -> dict | None:
    conditions: list[dict] = []
    if use_genre and genre:
        conditions.append({"genre": {"$eq": genre}})
    if use_industry and industry:
        conditions.append({"industry_category": {"$eq": industry}})
    if not conditions:
        return None
    return conditions[0] if len(conditions) == 1 else {"$and": conditions}


def _find_candidates(
    genre: str, industry: str, min_n: int, db_path: str | Path,
) -> tuple[str, dict | None, list[dict]]:
    """min_n 을 만족하는 첫 완화 수준의 (level, where, 후보 rows)를 반환한다."""
    fallback: tuple[str, dict | None, list[dict]] = ("global", None, [])
    for level, use_genre, use_industry in _RELAX_LEVELS:
        where = _build_where(use_genre, use_industry, genre, industry)
        if where is None and level != "global":
            continue  # 입력이 비어 해당 수준의 필터를 만들 수 없음
        rows = fetch_members("creative", where=where, db_path=db_path)
        if len(rows) >= min_n:
            return level, where, rows
        if rows and not fallback[2]:
            fallback = (level, where, rows)
    return fallback


def _rrf_scores(
    candidate_ids: set[int],
    queries: dict[str, str],
    where: dict | None,
    db_path: str | Path,
) -> dict[int, float]:
    """facet 별 유사도 순위를 RRF 로 병합한 video_id → score 맵을 만든다."""
    scores: dict[int, float] = {vid: 0.0 for vid in candidate_ids}
    for facet, text in queries.items():
        if not text:
            continue
        rows = query_facet(facet, text, n_results=len(candidate_ids), where=where, db_path=db_path)
        for rank, row in enumerate(rows):
            vid = row["video_id"]
            if vid in scores:
                scores[vid] += _FACET_WEIGHTS[facet] / (_RRF_K + rank + 1)
    return scores


def retrieve_segment(
    genre: str,
    industry: str,
    target_text: str,
    usp_text: str,
    min_n: int = 15,
    cap: int = 60,
    db_path: str | Path = "output/vector_db",
) -> dict:
    """세그먼트 멤버(video_id + 유사도 점수)와 완화 수준을 반환한다."""
    level, where, candidates = _find_candidates(genre, industry, min_n, db_path)
    if not candidates:
        return {"relax_level": level, "n_candidates": 0, "n_members": 0, "members": []}

    candidate_ids = {r["video_id"] for r in candidates}
    scores = _rrf_scores(candidate_ids, {"target": target_text, "usp": usp_text}, where, db_path)
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])[:cap]
    return {
        "relax_level": level,
        "n_candidates": len(candidates),
        "n_members": len(ranked),
        "members": [{"video_id": vid, "score": round(score, 6)} for vid, score in ranked],
    }
