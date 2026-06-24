"""ChromaDB video_category 컬렉션의 임베딩을 K-Means 로 클러스터링한다.

K 를 지정하거나 `--k auto` 로 silhouette score 최대값을 선택할 수 있다.
결과는 콘솔 요약 + JSON 파일로 저장한다.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import chromadb
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from evaluation.vector_store import _COLLECTION, get_embedding_function

_DEFAULT_DB = Path(__file__).parent.parent / "output" / "vector_db"
_DEFAULT_OUT = Path(__file__).parent.parent / "output" / "vector_db_clusters.json"
_K_SEARCH_MAX = 10


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ChromaDB 카테고리 컬렉션 클러스터링")
    p.add_argument("--db_path", type=Path, default=_DEFAULT_DB)
    p.add_argument("--collection", default=_COLLECTION)
    p.add_argument("--k", default="auto",
                   help="클러스터 수. 정수 또는 'auto' (silhouette 최대값으로 2..min(10, n//3))")
    p.add_argument("--out", type=Path, default=_DEFAULT_OUT, help="요약 JSON 저장 경로")
    p.add_argument("--seed", type=int, default=42)
    return p


def _load_collection(db_path: Path, name: str) -> dict:
    client = chromadb.PersistentClient(path=str(db_path))
    col = client.get_collection(name, embedding_function=get_embedding_function())
    data = col.get(include=["embeddings", "documents", "metadatas"])
    if data["embeddings"] is None or len(data["embeddings"]) == 0:
        print("[오류] 컬렉션이 비어 있습니다.", file=sys.stderr)
        sys.exit(1)
    return data


def _select_k(embeddings: np.ndarray, seed: int) -> int:
    """silhouette score 가 최대인 K 를 2..min(10, n//3) 범위에서 고른다."""
    n = embeddings.shape[0]
    upper = min(_K_SEARCH_MAX, max(2, n // 3))
    best_k, best_score = 2, -1.0
    print(f"  K 자동 선택 중 (범위 2..{upper})...")
    for k in range(2, upper + 1):
        km = KMeans(n_clusters=k, random_state=seed, n_init=10).fit(embeddings)
        score = silhouette_score(embeddings, km.labels_, metric="cosine")
        marker = "  ★" if score > best_score else ""
        print(f"    k={k:>2}: silhouette={score:+.4f}{marker}")
        if score > best_score:
            best_k, best_score = k, score
    print(f"  → 최적 K = {best_k} (silhouette={best_score:+.4f})")
    return best_k


def _summarize_cluster(
    cluster_id: int,
    member_idx: np.ndarray,
    data: dict,
    embeddings: np.ndarray,
    center: np.ndarray,
) -> dict:
    """클러스터 1개 요약 — 대표 멤버, 우세 카테고리, 모든 멤버 리스트."""
    metas = [data["metadatas"][i] for i in member_idx]
    industries = Counter(m.get("industry_category") for m in metas if m.get("industry_category"))
    products = Counter(m.get("product_category") for m in metas if m.get("product_category"))

    # centroid 최근접 = 대표
    dists = np.linalg.norm(embeddings[member_idx] - center, axis=1)
    rep_local = int(np.argmin(dists))
    rep_global = int(member_idx[rep_local])

    members = [
        {
            "video_id": metas[i].get("video_id"),
            "brand": metas[i].get("brand_name", ""),
            "industry": metas[i].get("industry_category", ""),
            "product_category": metas[i].get("product_category", ""),
        }
        for i in range(len(member_idx))
    ]
    return {
        "cluster_id": cluster_id,
        "size": len(member_idx),
        "dominant_industries": industries.most_common(3),
        "dominant_products": products.most_common(3),
        "representative": {
            "video_id": data["metadatas"][rep_global].get("video_id"),
            "brand": data["metadatas"][rep_global].get("brand_name", ""),
            "document_head": data["documents"][rep_global][:200],
        },
        "members": members,
    }


def _print_cluster(summary: dict) -> None:
    print(f"\n── Cluster {summary['cluster_id']}  ({summary['size']}건) ──")
    inds = ", ".join(f"{k}({v})" for k, v in summary["dominant_industries"])
    prods = ", ".join(f"{k}({v})" for k, v in summary["dominant_products"][:3])
    print(f"  산업: {inds}")
    print(f"  제품: {prods}")
    rep = summary["representative"]
    print(f"  대표: video_id={rep['video_id']}  brand={rep['brand']}")
    for m in summary["members"]:
        print(f"    - {m['video_id']:>4}  [{m['industry']:<18}] {m['product_category']}  ({m['brand'][:30]})")


def main() -> None:
    args = _build_parser().parse_args()
    data = _load_collection(args.db_path, args.collection)
    embeddings = np.array(data["embeddings"])
    n = embeddings.shape[0]
    print(f"[cluster] 컬렉션: {args.collection}  ({n}건, dim={embeddings.shape[1]})")

    k = _select_k(embeddings, args.seed) if args.k == "auto" else int(args.k)
    if not 2 <= k <= n - 1:
        print(f"[오류] K={k} 가 범위 [2, {n - 1}] 밖", file=sys.stderr)
        sys.exit(1)

    print(f"[cluster] K-Means 실행 (k={k})")
    km = KMeans(n_clusters=k, random_state=args.seed, n_init=10).fit(embeddings)
    score = silhouette_score(embeddings, km.labels_, metric="cosine")
    print(f"  silhouette (cosine) = {score:+.4f}")

    summaries: list[dict] = []
    for cid in range(k):
        member_idx = np.where(km.labels_ == cid)[0]
        summaries.append(_summarize_cluster(cid, member_idx, data, embeddings, km.cluster_centers_[cid]))

    summaries.sort(key=lambda s: -s["size"])
    for s in summaries:
        _print_cluster(s)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "k": k,
                "n": n,
                "silhouette_cosine": round(score, 4),
                "clusters": summaries,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\n[cluster] 저장: {args.out}")


if __name__ == "__main__":
    main()
