"""ad_visual_reference 컬렉션에서 자연어(한국어 포함) 쿼리로 비주얼 스타일이 비슷한 키프레임을 찾는다."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from db.chromadb.connection import db_path_for, get_client, get_clip_text_embedding_function

_DEFAULT_COLLECTION = "ad_visual_reference"


def search_visual(query_text: str, n_results: int = 5, collection: str = _DEFAULT_COLLECTION,
                   db_path: Path | str | None = None) -> list[dict]:
    """query_text 와 시각적으로 유사한 순으로 최대 n_results 건을 반환한다.

    db_path 를 안 주면 `data/<collection>/` 를 쓴다. 컬렉션의 embedding_function 이 CLIP
    텍스트 인코더로 등록돼 있어야 한다(db.chromadb.importers.keyframe_visual 로 적재한 컬렉션).
    """
    client = get_client(db_path if db_path is not None else db_path_for(collection))
    col = client.get_collection(collection, embedding_function=get_clip_text_embedding_function())
    n = min(n_results, col.count())
    if n == 0:
        return []
    raw = col.query(query_texts=[query_text], n_results=n, include=["metadatas", "distances"])
    return [
        {"video_id": meta.get("video_id"), "cut_index": meta.get("cut_index"),
         "image_path": meta.get("image_path"), "distance": round(dist, 4)}
        for meta, dist in zip(raw["metadatas"][0], raw["distances"][0])
    ]


def _print_results(results: list[dict]) -> None:
    if not results:
        print("검색 결과 없음.")
        return
    for i, r in enumerate(results, 1):
        print(f"[{i}] video_id={r['video_id']}  cut_index={r['cut_index']}  "
              f"거리={r['distance']:.4f}  path={r['image_path']}")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ad_visual_reference 비주얼(이미지) 유사도 검색")
    p.add_argument("--collection", default=_DEFAULT_COLLECTION, help="검색할 컬렉션명")
    p.add_argument("--query", required=True, help="자연어 검색 쿼리(한국어 가능)")
    p.add_argument("--n_results", type=int, default=5, help="반환 결과 수 (기본: 5)")
    p.add_argument("--db_path", type=Path, default=None,
                   help="ChromaDB 저장 경로(미지정 시 data/<collection>/)")
    p.add_argument("--json", action="store_true", dest="as_json", help="결과를 JSON으로 출력")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    results = search_visual(args.query, args.n_results, args.collection, args.db_path)
    if args.as_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        _print_results(results)


if __name__ == "__main__":
    main()
