"""ChromaDB 컬렉션과 자연어 쿼리를 지정하면 유사도 상위 레코드를 출력한다."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from db.chromadb.connection import DEFAULT_DB_PATH, get_client, get_collection


def search(collection_name: str, query_text: str, n_results: int = 5,
           db_path: Path | str = DEFAULT_DB_PATH) -> list[dict]:
    """query_text 와 유사도가 높은 순으로 최대 n_results 건을 반환한다."""
    client = get_client(db_path)
    col = get_collection(client, collection_name, with_embeddings=True)
    n = min(n_results, col.count())
    if n == 0:
        return []
    raw = col.query(query_texts=[query_text], n_results=n,
                     include=["documents", "metadatas", "distances"])
    return [
        {"id": rid, "metadata": meta, "document": doc, "distance": dist}
        for rid, meta, doc, dist in zip(
            raw["ids"][0], raw["metadatas"][0], raw["documents"][0], raw["distances"][0]
        )
    ]


def _print_results(results: list[dict]) -> None:
    if not results:
        print("검색 결과 없음.")
        return
    for i, r in enumerate(results, 1):
        print(f"\n[{i}] id={r['id']}  거리={r['distance']:.4f}")
        print("meta:", r["metadata"])
        print(f"     {r['document'][:300]}")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ChromaDB 컬렉션 자연어 유사도 검색")
    p.add_argument("--collection", required=True, help="검색할 컬렉션명")
    p.add_argument("--query", required=True, help="자연어 검색 쿼리")
    p.add_argument("--n_results", type=int, default=5, help="반환 결과 수 (기본: 5)")
    p.add_argument("--db_path", type=Path, default=DEFAULT_DB_PATH, help="ChromaDB 저장 경로")
    p.add_argument("--json", action="store_true", dest="as_json", help="결과를 JSON으로 출력")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    results = search(args.collection, args.query, args.n_results, args.db_path)
    if args.as_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        _print_results(results)


if __name__ == "__main__":
    main()
