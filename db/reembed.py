"""기존 video_category 컬렉션을 비우고 새 임베딩 모델로 재적재한다.

EMBEDDING_MODEL 을 바꾼 뒤 한 번만 실행하면 된다.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import chromadb

from evaluation.category.vector_store import (
    EMBEDDING_MODEL,
    _COLLECTION,
    get_embedding_function,
    upsert_batch,
)

_DEFAULT_DB = Path(__file__).parent.parent / "output" / "vector_db"
_DEFAULT_DATA_ROOT = Path(__file__).parent.parent.parent / "output" / "additional_0609" / "claude"


def _collect_records(data_root: Path) -> list[tuple[int, dict]]:
    records: list[tuple[int, dict]] = []
    for path in sorted(data_root.glob("*/category_analysis.json")):
        try:
            video_id = int(path.parent.name)
        except ValueError:
            print(f"  skip (non-numeric dir): {path.parent.name}", file=sys.stderr)
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if "error" in data:
            print(f"  skip (error): video_id={video_id} reason={data.get('error')}", file=sys.stderr)
            continue
        records.append((video_id, data))
    return records


def main() -> None:
    p = argparse.ArgumentParser(description="ChromaDB 컬렉션 재임베딩")
    p.add_argument("--db_path", type=Path, default=_DEFAULT_DB)
    p.add_argument("--collection", default=_COLLECTION)
    p.add_argument("--data_root", type=Path, default=_DEFAULT_DATA_ROOT,
                   help="<data_root>/<video_id>/category_analysis.json 를 스캔")
    args = p.parse_args()

    print(f"[reembed] model={EMBEDDING_MODEL}")
    print(f"[reembed] db={args.db_path}")
    print(f"[reembed] data_root={args.data_root}")

    if not args.data_root.exists():
        print(f"[오류] data_root 없음: {args.data_root}", file=sys.stderr)
        sys.exit(1)

    records = _collect_records(args.data_root)
    if not records:
        print("[오류] 적재할 category_analysis.json 없음", file=sys.stderr)
        sys.exit(1)
    print(f"[reembed] 적재 대상: {len(records)} 건")

    client = chromadb.PersistentClient(path=str(args.db_path))
    try:
        client.delete_collection(args.collection)
        print(f"[reembed] 기존 컬렉션 삭제: {args.collection}")
    except Exception as e:
        print(f"[reembed] 컬렉션 없음 (skip): {e}")

    # 새 임베딩 함수로 컬렉션 재생성 + 적재
    ef = get_embedding_function()
    client.create_collection(
        args.collection, embedding_function=ef, metadata={"hnsw:space": "cosine"}
    )
    upsert_batch(records, db_path=args.db_path, collection_name=args.collection)
    print("[reembed] 완료")


if __name__ == "__main__":
    main()
