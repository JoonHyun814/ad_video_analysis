"""G5 — 생성 컨셉이 클리셰 결정을 실제로 지켰는지 임베딩 거리로 검증한다 (LLM 미사용).

각 컨셉의 creative_summary 를 코퍼스와 같은 모델(bge-m3)로 임베딩해
세그먼트 클리셰 클러스터 centroid 와의 cosine distance 를 잰다.
avoid/subvert 로 결정된 클러스터에 threshold 이내로 근접한 컨셉은 violation 으로 표시한다.
"""
import numpy as np

from evaluation.category.vector_store import get_embedding_function

_AVOID_DECISIONS = ("avoid", "subvert")


def _concept_text(concept: dict) -> str:
    parts = [concept.get("creative_summary", ""), concept.get("hook", ""),
             concept.get("visual_language", "")]
    return "\n".join(p for p in parts if p)


def _decision_map(g3: dict) -> dict[str, str]:
    return {
        d["pattern"]: d["decision"]
        for d in g3.get("decisions", [])
        if d.get("pattern") and d.get("decision")
    }


def _cluster_decision(cluster: dict, decisions: dict[str, str]) -> str | None:
    """클러스터 우세 패턴 중 G3 결정이 있는 첫 패턴의 decision 을 반환한다."""
    for pattern in cluster.get("dominant_patterns", []):
        if pattern in decisions:
            return decisions[pattern]
    return None


def _cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 1.0
    return 1.0 - float(np.dot(a, b)) / denom


def _check_concept(concept: dict, embedding: np.ndarray, clusters: list[dict],
                   decisions: dict[str, str], avoid_distance: float) -> dict:
    """컨셉 1개를 모든 클러스터에 대해 거리 검사한다."""
    checks: list[dict] = []
    for cluster in clusters:
        centroid = np.array(cluster["centroid"])
        dist = _cosine_distance(embedding, centroid)
        decision = _cluster_decision(cluster, decisions)
        violated = decision in _AVOID_DECISIONS and dist < avoid_distance
        checks.append({
            "cluster_id": cluster["cluster_id"],
            "dominant_patterns": cluster.get("dominant_patterns", []),
            "decision": decision,
            "distance": round(dist, 4),
            "ok": not violated,
        })
    return {
        "id": concept.get("id"),
        "title": concept.get("title"),
        "cluster_checks": checks,
        "verdict": "pass" if all(c["ok"] for c in checks) else "violation",
    }


def verify_concepts(g4: dict, report: dict, g3: dict, avoid_distance: float = 0.35) -> dict:
    """G4 컨셉 5개를 클리셰 클러스터 거리로 검증한 결과를 반환한다."""
    concepts = g4.get("concepts", [])
    clusters = [c for c in report.get("clusters", []) if c.get("centroid")]
    if not concepts:
        return {"error": "no_concepts", "results": [], "passed": []}
    if not clusters:
        return {"note": "세그먼트 클러스터 없음 (표본 부족) — 거리 검증 생략",
                "results": [], "passed": [c.get("id") for c in concepts]}

    ef = get_embedding_function()
    embeddings = np.array(ef([_concept_text(c) for c in concepts]))
    decisions = _decision_map(g3)
    results = [
        _check_concept(c, embeddings[i], clusters, decisions, avoid_distance)
        for i, c in enumerate(concepts)
    ]
    return {
        "avoid_distance": avoid_distance,
        "results": results,
        "passed": [r["id"] for r in results if r["verdict"] == "pass"],
    }
