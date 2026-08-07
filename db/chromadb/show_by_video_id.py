"""ChromaDB 컬렉션과 video_id 를 지정하면 해당 video_id 의 레코드를 전부 출력한다."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from db.chromadb.connection import DEFAULT_DB_PATH, get_client


def fetch_by_video_id(collection_name: str, video_id: int,
                       db_path: Path | str = DEFAULT_DB_PATH) -> list[dict]:
    """collection_name 에서 metadata.video_id == video_id 인 레코드를 전부 반환한다."""
    client = get_client(db_path)
    col = client.get_collection(collection_name)
    data = col.get(where={"video_id": video_id}, include=["documents", "metadatas"])
    return [
        {"id": rid, "metadata": meta, "document": doc}
        for rid, meta, doc in zip(data["ids"], data["metadatas"], data["documents"])
    ]


def _print_records(records: list[dict]) -> None:
    if not records:
        print("해당 video_id 레코드 없음.")
        return
    for r in records:
        print(f"\n--- {r['id']} ---")
        print("meta:", r["metadata"])
        print("<doc>")
        print(r["document"])


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ChromaDB 컬렉션에서 video_id 로 레코드 조회")
    p.add_argument("--collection", required=True, help="조회할 컬렉션명")
    p.add_argument("--video_id", required=True, type=int, help="조회할 video_id")
    p.add_argument("--db_path", type=Path, default=DEFAULT_DB_PATH, help="ChromaDB 저장 경로")
    p.add_argument("--json", action="store_true", dest="as_json", help="결과를 JSON으로 출력")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    records = fetch_by_video_id(args.collection, args.video_id, args.db_path)
    if args.as_json:
        print(json.dumps(records, ensure_ascii=False, indent=2))
    else:
        _print_records(records)


if __name__ == "__main__":
    main()
