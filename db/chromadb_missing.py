"""video_uploads 에는 있지만 ChromaDB 컬렉션에는 없는 video_id 목록을 출력한다."""
import argparse
import sys
from pathlib import Path

# db/ 직접 실행 시 상위 패키지를 찾을 수 있도록 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

import chromadb

from db.connection import get_connection

_DEFAULT_DB = Path(__file__).parent.parent / "output" / "vector_db"
_DEFAULT_COLLECTION = "video_category"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="video_uploads 에는 있는데 ChromaDB 에는 없는 video_id 출력"
    )
    p.add_argument("--db_path", type=Path, default=_DEFAULT_DB, help="ChromaDB 저장 경로")
    p.add_argument("--collection", default=_DEFAULT_COLLECTION, help="ChromaDB 컬렉션명")
    p.add_argument("--table", default="video_uploads", help="비교 기준 MySQL 테이블명")
    return p


def _fetch_mysql_ids(table: str) -> set[int]:
    """MySQL <table>.id 전체를 집합으로 반환한다."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT id FROM `{table}`")
        return {int(row[0]) for row in cursor.fetchall() if row[0] is not None}


def _fetch_chroma_video_ids(db_path: Path, collection: str) -> set[int]:
    """ChromaDB 컬렉션의 metadata.video_id 전체를 집합으로 반환한다."""
    client = chromadb.PersistentClient(path=str(db_path))
    col = client.get_or_create_collection(collection)
    data = col.get(include=["metadatas"])
    return {
        int(m["video_id"])
        for m in data["metadatas"]
        if m is not None and m.get("video_id") is not None
    }


def main() -> None:
    args = _build_parser().parse_args()

    mysql_ids = _fetch_mysql_ids(args.table)
    chroma_ids = _fetch_chroma_video_ids(args.db_path, args.collection)
    missing = sorted(mysql_ids - chroma_ids)

    print(f"MySQL {args.table}: {len(mysql_ids)}건")
    print(f"ChromaDB {args.collection}: {len(chroma_ids)}건")
    print(f"미적재 (DB - vector): {len(missing)}건")
    for vid in missing:
        print(vid)


if __name__ == "__main__":
    main()
