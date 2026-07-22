"""ChromaDB video_category 컬렉션의 임베딩을 K-Means 로 클러스터링한다.

K 를 지정하거나 `--k auto` 로 silhouette score 최대값을 선택할 수 있다.
--fields 로 기준 컬럼을 지정하면 해당 필드만 추출해 재임베딩 후 클러스터링한다.
결과는 콘솔 요약 + JSON + CSV 파일로 저장한다.
"""
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import chromadb
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from evaluation.category.vector_store import _COLLECTION, _FIELD_LABELS, get_embedding_function

_DEFAULT_DB = Path(__file__).parent.parent / "output" / "vector_db"
_DEFAULT_OUT_DIR = Path(__file__).parent.parent / "output"
_K_SEARCH_MAX = 10

# 필드명 → 문서 내 한글 라벨 (vector_store._FIELD_LABELS 과 동일)
_AVAILABLE_FIELDS = list(_FIELD_LABELS.keys())


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ChromaDB 카테고리 컬렉션 클러스터링")
    p.add_argument("--db_path", type=Path, default=_DEFAULT_DB)
    p.add_argument("--collection", default=_COLLECTION)
    p.add_argument("--k", default="auto",
                   help="클러스터 수. 정수 또는 'auto' (silhouette 최대값으로 2..min(10, n//3))")
    p.add_argument("--fields", default=None,
                   help=(
                       "클러스터링 기준 필드 (콤마 구분). 미지정 시 저장된 임베딩 전체 사용.\n"
                       f"사용 가능: {', '.join(_AVAILABLE_FIELDS)}\n"
                       "예) --fields target_persona\n"
                       "    --fields target_persona,key_message"
                   ))
    p.add_argument("--out_dir", type=Path, default=_DEFAULT_OUT_DIR, help="결과 파일 저장 디렉토리")
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


def _filter_document(document: str, labels: list[str]) -> str:
    """document 텍스트에서 지정 라벨 행만 추출해 재구성한다."""
    prefixes = tuple(f"{label}:" for label in labels)
    lines = [line for line in document.splitlines() if line.startswith(prefixes)]
    return "\n".join(lines)


def _reembed(data: dict, field_names: list[str]) -> np.ndarray:
    """지정 필드만 추출해 재임베딩한 벡터 행렬을 반환한다."""
    labels = [_FIELD_LABELS[f] for f in field_names]
    filtered_docs = [_filter_document(d, labels) for d in data["documents"]]

    empty_idx = [i for i, d in enumerate(filtered_docs) if not d.strip()]
    if empty_idx:
        print(f"  [경고] {len(empty_idx)}건에서 지정 필드 값 없음 → 빈 문서로 임베딩", file=sys.stderr)

    ef = get_embedding_function()
    return np.array(ef(filtered_docs))


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


def _parse_field(document: str, label: str) -> str | None:
    """document 텍스트에서 특정 라벨 값을 추출한다."""
    prefix = f"{label}:"
    for line in document.splitlines():
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip() or None
    return None


def _parse_narrative(document: str) -> str | None:
    return _parse_field(document, "서사 구조")


def _parse_creative_style(document: str) -> str | None:
    return _parse_field(document, "크리에이티브 스타일")


def _summarize_cluster(
    cluster_id: int,
    member_idx: np.ndarray,
    data: dict,
    embeddings: np.ndarray,
    center: np.ndarray,
) -> dict:
    """클러스터 1개 요약 — 대표 멤버, 우세 카테고리, 브랜드·서사·크리에이티브 분포."""
    metas = [data["metadatas"][i] for i in member_idx]
    docs = [data["documents"][i] for i in member_idx]

    industries = Counter(m.get("industry_category") for m in metas if m.get("industry_category"))
    products = Counter(m.get("product_category") for m in metas if m.get("product_category"))
    brands = Counter(m.get("industry_category") for m in metas if m.get("industry_category"))
    narratives = Counter(_parse_narrative(d) for d in docs if _parse_narrative(d))
    creative_styles = Counter(_parse_creative_style(d) for d in docs if _parse_creative_style(d))

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
        "brand_category_distribution": brands.most_common(),
        "narrative_distribution": narratives.most_common(),
        "creative_style_distribution": creative_styles.most_common(),
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

    print(f"  브랜드 카테고리 분포:")
    for cat, cnt in summary["brand_category_distribution"]:
        print(f"    {cnt:>3}건  {cat}")

    print(f"  서사 분포:")
    for narrative, cnt in summary["narrative_distribution"]:
        print(f"    {cnt:>3}건  {narrative}")

    print(f"  크리에이티브 스타일 분포:")
    for style, cnt in summary["creative_style_distribution"]:
        print(f"    {cnt:>3}건  {style}")

    rep = summary["representative"]
    print(f"  대표: video_id={rep['video_id']}  brand={rep['brand']}")
    for m in summary["members"]:
        print(f"    - {m['video_id']:>4}  [{m['industry']:<18}] {m['product_category']}  ({m['brand'][:30]})")


def _write_csv(path: Path, rows: list[list], header: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def _save_count_table(summaries: list[dict], path: Path) -> None:
    rows = [[s["cluster_id"], s["size"]] for s in summaries]
    _write_csv(path, rows, ["cluster_id", "count"])


def _save_brand_table(summaries: list[dict], path: Path) -> None:
    rows = [
        [s["cluster_id"], cat, cnt]
        for s in summaries
        for cat, cnt in s["brand_category_distribution"]
    ]
    _write_csv(path, rows, ["cluster_id", "brand_category", "count"])


def _save_narrative_table(summaries: list[dict], path: Path) -> None:
    rows = [
        [s["cluster_id"], narrative, cnt]
        for s in summaries
        for narrative, cnt in s["narrative_distribution"]
    ]
    _write_csv(path, rows, ["cluster_id", "narrative", "count"])


def _save_creative_style_table(summaries: list[dict], path: Path) -> None:
    rows = [
        [s["cluster_id"], style, cnt]
        for s in summaries
        for style, cnt in s["creative_style_distribution"]
    ]
    _write_csv(path, rows, ["cluster_id", "creative_style", "count"])


def _output_paths(out_dir: Path, suffix: str) -> dict[str, Path]:
    """출력 파일 경로를 suffix 포함해 일괄 생성한다."""
    return {
        "json": out_dir / f"vector_db_clusters{suffix}.json",
        "counts": out_dir / f"cluster_counts{suffix}.csv",
        "brand": out_dir / f"cluster_brand_category_dist{suffix}.csv",
        "narrative": out_dir / f"cluster_narrative_dist{suffix}.csv",
        "creative": out_dir / f"cluster_creative_style_dist{suffix}.csv",
    }


def main() -> None:
    args = _build_parser().parse_args()

    # --fields 파싱 및 검증
    field_names: list[str] | None = None
    if args.fields:
        field_names = [f.strip() for f in args.fields.split(",") if f.strip()]
        invalid = [f for f in field_names if f not in _FIELD_LABELS]
        if invalid:
            print(f"[오류] 알 수 없는 필드: {invalid}", file=sys.stderr)
            print(f"  사용 가능: {', '.join(_AVAILABLE_FIELDS)}", file=sys.stderr)
            sys.exit(1)

    data = _load_collection(args.db_path, args.collection)
    n = len(data["embeddings"])

    if field_names:
        print(f"[cluster] 기준 필드: {field_names} → 재임베딩 중...")
        embeddings = _reembed(data, field_names)
        suffix = "__" + "_".join(field_names)
    else:
        embeddings = np.array(data["embeddings"])
        suffix = ""

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

    paths = _output_paths(args.out_dir, suffix)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    paths["json"].write_text(
        json.dumps(
            {
                "k": k,
                "n": n,
                "silhouette_cosine": round(score, 4),
                "fields": field_names,
                "clusters": summaries,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    _save_count_table(summaries, paths["counts"])
    _save_brand_table(summaries, paths["brand"])
    _save_narrative_table(summaries, paths["narrative"])
    _save_creative_style_table(summaries, paths["creative"])

    for p in paths.values():
        print(f"[cluster] 저장: {p}")


if __name__ == "__main__":
    main()
