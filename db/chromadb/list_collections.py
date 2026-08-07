"""ChromaDB 컬렉션(테이블) 목록과 각 컬렉션의 레코드 수를 출력한다."""
from __future__ import annotations

import argparse
from pathlib import Path

from db.chromadb.connection import DATA_ROOT, get_client


def list_collections(db_path: Path | str | None = None) -> list[tuple[str, int]]:
    """(컬렉션명, 레코드 수) 목록을 반환한다.

    db_path 를 주면 그 경로 하나만 조회한다(레거시 저장소 등 예외 경로 확인용). 안 주면
    DATA_ROOT(data/) 아래 `chroma.sqlite3` 가 있는 디렉터리(=컬렉션명과 같은 폴더명 하나당
    ChromaDB 저장소 하나 컨벤션)를 전부 훑는다 — 컨벤션을 안 따르는 다른 데이터 폴더
    (예: data/ad_concept_production)에는 손대지 않는다.
    """
    if db_path is not None:
        client = get_client(db_path)
        return [(c.name, client.get_collection(c.name).count()) for c in client.list_collections()]

    rows: list[tuple[str, int]] = []
    if not DATA_ROOT.exists():
        return rows
    for sub in sorted(DATA_ROOT.iterdir()):
        if not sub.is_dir() or not (sub / "chroma.sqlite3").exists():
            continue
        client = get_client(sub)
        for c in client.list_collections():
            rows.append((c.name, client.get_collection(c.name).count()))
    return rows


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ChromaDB 컬렉션 목록 출력")
    p.add_argument("--db_path", type=Path, default=None,
                   help="ChromaDB 저장 경로(미지정 시 data/ 아래 전체 스캔)")
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
