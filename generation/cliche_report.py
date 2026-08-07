"""세그먼트의 크리에이티브 속성 분포·임베딩 밀도를 분석해 클리셰 리포트를 만든다 (G2 후반부, LLM 미사용).

- 범주형 히스토그램: 점유율에 따라 category_code(관행) / creative_cliche(과밀) / whitespace(공백) 분류
- 임베딩 군집: ad_creative 임베딩 K-Means, 큰 밀집 클러스터 = 클리셰 패턴 (centroid 는 G5 검증에 재사용)
"""
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from db.chromadb.importers.facets import fetch_members

# CM3 의 diverse_appeal/diverse_execution 렌즈가 카테고리별로 1건씩 표본 추출할 때 순회할 값 목록
# ("other" 는 창의적 다각화 신호로 쓸모가 적어 제외한다).
APPEAL_TYPE_CHOICES = (
    "humor", "parody_wordplay", "maternal_love", "vanity", "fear", "sex_appeal",
    "comparison", "rational_info", "emotional_storytelling", "testimonial",
    "scarcity_urgency", "nostalgia", "aspiration",
)
EXECUTION_STYLE_CHOICES = ("slice_of_life", "scientific_evidence", "fantasy", "fashion")

_ATTR_CHOICES: dict[str, tuple[str, ...]] = {
    "appeal_type": APPEAL_TYPE_CHOICES,
    "execution_style": EXECUTION_STYLE_CHOICES,
    "perceived_value": ("functional_quality", "functional_price", "emotional", "social"),
    "message_strategy": ("informational", "transformational"),
}
_MIN_CLUSTER_N = 8
_K_MAX = 6
_DENSE_SHARE = 0.4
_EXAMPLE_DOC_CHARS = 400


def _histogram(metas: list[dict], field: str) -> list[dict]:
    counts = Counter(m.get(field) for m in metas if m.get(field))
    total = sum(counts.values())
    return [
        {"value": val, "count": cnt, "share": round(cnt / total, 3)}
        for val, cnt in counts.most_common()
    ] if total else []


def _classify_attr(field: str, hist: list[dict], code_share: float, cliche_share: float) -> dict:
    """히스토그램을 category_code / creative_cliche / whitespace 로 분류한다."""
    codes = [h for h in hist if h["share"] >= code_share]
    cliches = [h for h in hist if cliche_share <= h["share"] < code_share]
    used = {h["value"] for h in hist}
    whitespace = [v for v in _ATTR_CHOICES[field] if v not in used]
    tag = lambda hs: [{"pattern": f"{field}={h['value']}", **h} for h in hs]
    return {"category_codes": tag(codes), "creative_cliches": tag(cliches),
            "whitespace": [f"{field}={v}" for v in whitespace]}


def _select_k(embeddings: np.ndarray, seed: int) -> int:
    n = embeddings.shape[0]
    upper = min(_K_MAX, max(2, n // 4))
    best_k, best_score = 2, -1.0
    for k in range(2, upper + 1):
        km = KMeans(n_clusters=k, random_state=seed, n_init=10).fit(embeddings)
        score = silhouette_score(embeddings, km.labels_, metric="cosine")
        if score > best_score:
            best_k, best_score = k, score
    return best_k


def _summarize_cluster(cid: int, member_idx: np.ndarray, rows: list[dict],
                       embeddings: np.ndarray, center: np.ndarray, n_total: int) -> dict:
    """클러스터 1개 요약 — 우세 패턴·대표 연출 예시·centroid."""
    metas = [rows[i]["metadata"] for i in member_idx]
    dists = np.linalg.norm(embeddings[member_idx] - center, axis=1)
    rep = rows[int(member_idx[int(np.argmin(dists))])]
    dominant = [
        f"{field}={hist[0]['value']}"
        for field in _ATTR_CHOICES
        if (hist := _histogram(metas, field)) and hist[0]["share"] >= 0.5
    ]
    return {
        "cluster_id": cid,
        "size": int(len(member_idx)),
        "share": round(len(member_idx) / n_total, 3),
        "is_dense": len(member_idx) / n_total >= _DENSE_SHARE,
        "dominant_patterns": dominant,
        "example": {"video_id": rep["video_id"], "document": rep["document"][:_EXAMPLE_DOC_CHARS]},
        "member_ids": [rows[i]["video_id"] for i in member_idx],
        "centroid": [round(float(x), 6) for x in center],
    }


def _cluster_creative(rows: list[dict], seed: int) -> list[dict]:
    """세그먼트 크리에이티브 임베딩을 군집화한다. 표본이 작으면 생략."""
    if len(rows) < _MIN_CLUSTER_N:
        return []
    embeddings = np.array([r["embedding"] for r in rows])
    k = _select_k(embeddings, seed)
    km = KMeans(n_clusters=k, random_state=seed, n_init=10).fit(embeddings)
    summaries = [
        _summarize_cluster(cid, np.where(km.labels_ == cid)[0], rows, embeddings,
                           km.cluster_centers_[cid], len(rows))
        for cid in range(k)
    ]
    return sorted(summaries, key=lambda s: -s["size"])


def build_report(
    segment: dict,
    code_share: float = 0.75,
    cliche_share: float = 0.40,
    seed: int = 42,
    db_path: str | Path | None = None,
) -> dict:
    """세그먼트 멤버의 분포·군집을 분석한 클리셰 리포트를 만든다."""
    video_ids = [m["video_id"] for m in segment.get("members", [])]
    rows = fetch_members("creative", video_ids=video_ids, include_embeddings=True,
                         db_path=db_path) if video_ids else []
    metas = [r["metadata"] for r in rows]

    report: dict = {
        "n": len(rows),
        "relax_level": segment.get("relax_level"),
        "n_candidates": segment.get("n_candidates"),
        "thresholds": {"code_share": code_share, "cliche_share": cliche_share},
        "histograms": {f: _histogram(metas, f) for f in _ATTR_CHOICES},
        "category_codes": [], "creative_cliches": [], "whitespace": [],
    }
    for field in _ATTR_CHOICES:
        cls = _classify_attr(field, report["histograms"][field], code_share, cliche_share)
        report["category_codes"] += cls["category_codes"]
        report["creative_cliches"] += cls["creative_cliches"]
        report["whitespace"] += cls["whitespace"]
    report["clusters"] = _cluster_creative(rows, seed)
    return report


def report_for_prompt(report: dict) -> dict:
    """LLM 프롬프트 주입용 — centroid·멤버 목록을 제거한 경량 리포트."""
    slim = {k: v for k, v in report.items() if k != "clusters"}
    slim["clusters"] = [
        {k: v for k, v in c.items() if k not in ("centroid", "member_ids")}
        for c in report.get("clusters", [])
    ]
    return slim
