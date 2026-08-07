"""<data_root>/<video_id>/scenario_analysis.json 를 스캔해 scenario 컬렉션에 적재한다.

concept/narrative/key_messages/production_notes 만 자연어 검색용 문서 텍스트로 임베딩하고,
cast/scenes 는 원문 대신 개수(cast_count/scenes_count)만 메타데이터로 남긴다 — 캐스팅
설명·씬 비트 원문까지 넣으면 문서가 지나치게 길어져 임베딩 품질이 흐려지기 때문이다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from db.chromadb.connection import get_client, get_or_create_collection
from evaluation.category.vector_store import get_embedding_function

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DEFAULT_DATA_ROOT = _PROJECT_ROOT / "output" / "total"
_DEFAULT_DB_PATH = _PROJECT_ROOT / "data" / "scenario"
_COLLECTION = "scenario_analysis"


def _collect_records(data_root: Path) -> list[tuple[int, dict]]:
    """유효한 scenario_analysis.json 만 (video_id, data) 목록으로 모은다."""
    records: list[tuple[int, dict]] = []
    for path in sorted(data_root.glob("*/scenario_analysis.json")):
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


def _build_document(scenario: dict) -> str:
    """title/brand/concept/narrative/key_messages/production_notes 를 임베딩 텍스트로 합친다."""
    lines = []
    if scenario.get("title"):
        lines.append(f"title: {scenario['title']}")
    if scenario.get("brand"):
        lines.append(f"brand: {scenario['brand']}")
    if scenario.get("concept"):
        lines.append(f"concept: {scenario['concept']}")
    if scenario.get("narrative"):
        lines.append(f"narrative: {scenario['narrative']}")
    key_messages = scenario.get("key_messages") or []
    if key_messages:
        lines.append("key_messages:\n" + "\n".join(f"- {m}" for m in key_messages))
    if scenario.get("production_notes"):
        lines.append(f"production_notes: {scenario['production_notes']}")
    return "\n\n".join(lines)


def _build_metadata(video_id: int, scenario: dict) -> dict[str, Any]:
    """video_id/title/brand 와 cast·scenes 개수만 메타데이터로 저장한다."""
    return {
        "video_id": video_id,
        "title": scenario.get("title") or "",
        "brand": scenario.get("brand") or "",
        "cast_count": len(scenario.get("cast") or []),
        "scenes_count": len(scenario.get("scenes") or []),
    }


def upsert_batch(records: list[tuple[int, dict]], db_path: Path, collection: str) -> None:
    """복수 scenario_analysis 결과를 한 번에 upsert 한다."""
    client = get_client(db_path)
    col = get_or_create_collection(client, collection, embedding_function=get_embedding_function())
    ids = [f"scn:{vid}" for vid, _ in records]
    docs = [_build_document(scn) for _, scn in records]
    metas = [_build_metadata(vid, scn) for vid, scn in records]
    col.upsert(ids=ids, documents=docs, metadatas=metas)
    print(f"[scenario] {len(ids)}건 upsert 완료 (collection={collection}, db={db_path})")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="scenario_analysis.json → ChromaDB 적재")
    p.add_argument("--data_root", type=Path, default=_DEFAULT_DATA_ROOT,
                   help="<data_root>/<video_id>/scenario_analysis.json 스캔")
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
        print("[오류] 적재할 scenario_analysis.json 없음", file=sys.stderr)
        sys.exit(1)
    print(f"[scenario] 적재 대상: {len(records)}건  db={args.db_path}")

    if args.rebuild:
        client = get_client(args.db_path)
        try:
            client.delete_collection(args.collection)
            print(f"[scenario] 기존 컬렉션 삭제: {args.collection}")
        except Exception:
            pass

    upsert_batch(records, args.db_path, args.collection)


if __name__ == "__main__":
    main()
