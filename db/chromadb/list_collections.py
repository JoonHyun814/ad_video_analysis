"""ChromaDB 컬렉션(테이블) 목록과 각 컬렉션의 레코드 수를 출력한다."""
from __future__ import annotations

import argparse
from pathlib import Path

from db.chromadb.connection import DEFAULT_DB_PATH, get_client


def list_collections(db_path: Path | str = DEFAULT_DB_PATH) -> list[tuple[str, int]]:
    """(컬렉션명, 레코드 수) 목록을 반환한다."""
    client = get_client(db_path)
    return [(c.name, client.get_collection(c.name).count()) for c in client.list_collections()]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ChromaDB 컬렉션 목록 출력")
    p.add_argument("--db_path", type=Path, default=DEFAULT_DB_PATH, help="ChromaDB 저장 경로")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    rows = list_collections(args.db_path)
    if not rows:
        print("컬렉션 없음.")
        return
    for name, count in rows:
        print(f"{name}  ({count}건)")


if __name__ == "__main__":
    main()
