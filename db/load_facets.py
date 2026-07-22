"""<data_root>/<video_id>/concept_evaluation.json 을 스캔해 facet 컬렉션 3개에 일괄 적재한다.

ad_target / ad_usp / ad_creative 컬렉션을 처음 구축하거나 전체 재적재할 때 1회 실행한다.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import chromadb

from evaluation.concept.facet_vector_store import COLLECTIONS, upsert_facet_batch
from evaluation.category.vector_store import EMBEDDING_MODEL

_DEFAULT_DB = Path(__file__).parent.parent / "output" / "vector_db"
_DEFAULT_DATA_ROOT = Path(__file__).parent.parent / "output" / "total"


def _collect_records(data_root: Path) -> list[tuple[int, dict]]:
    """유효한 concept_evaluation.json 만 (video_id, concept) 목록으로 모은다."""
    records: list[tuple[int, dict]] = []
    for path in sorted(data_root.glob("*/concept_evaluation.json")):
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


def _drop_collections(db_path: Path) -> None:
    client = chromadb.PersistentClient(path=str(db_path))
    for name in COLLECTIONS.values():
        try:
            client.delete_collection(name)
            print(f"[load_facets] 기존 컬렉션 삭제: {name}")
        except Exception:
            pass


def main() -> None:
    p = argparse.ArgumentParser(description="concept_evaluation → facet 컬렉션 일괄 적재")
    p.add_argument("--db_path", type=Path, default=_DEFAULT_DB)
    p.add_argument("--data_root", type=Path, default=_DEFAULT_DATA_ROOT,
                   help="<data_root>/<video_id>/concept_evaluation.json 스캔")
    p.add_argument("--rebuild", action="store_true", help="기존 facet 컬렉션 삭제 후 재적재")
    args = p.parse_args()

    print(f"[load_facets] model={EMBEDDING_MODEL}")
    print(f"[load_facets] db={args.db_path}")
    print(f"[load_facets] data_root={args.data_root}")

    if not args.data_root.exists():
        print(f"[오류] data_root 없음: {args.data_root}", file=sys.stderr)
        sys.exit(1)

    records = _collect_records(args.data_root)
    if not records:
        print("[오류] 적재할 concept_evaluation.json 없음", file=sys.stderr)
        sys.exit(1)
    print(f"[load_facets] 적재 대상: {len(records)}건")

    if args.rebuild:
        _drop_collections(args.db_path)

    upsert_facet_batch(records, db_path=args.db_path)
    print("[load_facets] 완료")


if __name__ == "__main__":
    main()
