"""<data_root>/<video_id>/category_analysis.json 를 스캔해 category 컬렉션에 적재한다.

category_analysis.json 의 전체 필드(스키마)를 그대로 문서 텍스트 + 메타데이터로 임베딩한다
— 필드를 고르지 않고 `_meta` 를 뺀 나머지 전부를 쓰므로 스키마가 늘어나도 코드 수정이
필요 없다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from db.chromadb.connection import db_path_for, get_client, get_embedding_function, get_or_create_collection

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DEFAULT_DATA_ROOT = _PROJECT_ROOT / "output" / "total"
_COLLECTION = "category_analysis"
_DEFAULT_DB_PATH = db_path_for(_COLLECTION)


def _collect_records(data_root: Path) -> list[tuple[int, dict]]:
    """유효한 category_analysis.json 만 (video_id, data) 목록으로 모은다."""
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


def _scalar(value: Any) -> Any:
    """ChromaDB 메타데이터는 str/int/float/bool 만 허용 — 그 외 타입은 JSON 문자열로 변환."""
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    return json.dumps(value, ensure_ascii=False)


def _build_document(category: dict) -> str:
    """`_meta` 를 제외한 전체 필드를 `key: value` 줄로 직렬화해 임베딩 대상 텍스트를 만든다."""
    lines = [
        f"{key}: {value}"
        for key, value in category.items()
        if key != "_meta" and value not in (None, "")
    ]
    return "\n".join(lines)


def _build_metadata(video_id: int, category: dict) -> dict[str, Any]:
    """`_meta` 를 제외한 전체 필드를 메타데이터로 저장한다(video_id 는 폴더명 기준으로 덮어씀)."""
    meta: dict[str, Any] = {key: _scalar(value) for key, value in category.items() if key != "_meta"}
    meta["video_id"] = video_id
    return meta


def upsert_batch(records: list[tuple[int, dict]], db_path: Path, collection: str) -> None:
    """복수 category_analysis 결과를 한 번에 upsert 한다."""
    client = get_client(db_path)
    col = get_or_create_collection(client, collection, embedding_function=get_embedding_function())
    ids = [f"cat:{vid}" for vid, _ in records]
    docs = [_build_document(cat) for _, cat in records]
    metas = [_build_metadata(vid, cat) for vid, cat in records]
    col.upsert(ids=ids, documents=docs, metadatas=metas)
    print(f"[category] {len(ids)}건 upsert 완료 (collection={collection}, db={db_path})")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="category_analysis.json → ChromaDB 적재")
    p.add_argument("--data_root", type=Path, default=_DEFAULT_DATA_ROOT,
                   help="<data_root>/<video_id>/category_analysis.json 스캔")
    p.add_argument("--db_path", type=Path, default=_DEFAULT_DB_PATH, help="ChromaDB 저장 경로")
    p.add_argument("--collection", default=_COLLECTION)
    p.add_argument("--rebuild", action="store_true", help="기존 컬렉션 삭제 후 재적재")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    if not args.data_root.exists():
        print(f"[오류] data_root 없음: {args.data_root}", file=sys.stderr)
        sys.exit(1)

    records = _collect_records(args.data_root)
    if not records:
        print("[오류] 적재할 category_analysis.json 없음", file=sys.stderr)
        sys.exit(1)
    print(f"[category] 적재 대상: {len(records)}건  db={args.db_path}")

    if args.rebuild:
        client = get_client(args.db_path)
        try:
            client.delete_collection(args.collection)
            print(f"[category] 기존 컬렉션 삭제: {args.collection}")
        except Exception:
            pass

    upsert_batch(records, args.db_path, args.collection)


if __name__ == "__main__":
    main()
