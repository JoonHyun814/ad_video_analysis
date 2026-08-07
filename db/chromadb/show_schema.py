"""ChromaDB 컬렉션 하나를 지정하면 메타데이터 스키마(필드·타입·예시)와 적재 데이터 수를 출력한다.

ChromaDB 는 고정 스키마가 없으므로, 샘플 레코드의 metadata 키를 모아 관측된 필드 목록으로
"스키마"를 추론한다(레코드마다 record_kind 등에 따라 필드 구성이 다를 수 있다).
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from db.chromadb.connection import db_path_for, get_client


def inspect_schema(collection_name: str, db_path: Path | str | None = None,
                    sample_size: int = 500) -> dict[str, Any]:
    """count 와, 샘플 기준 메타데이터 필드별 타입/예시값/등장 빈도를 반환한다.

    db_path 를 안 주면 `data/<collection_name>/` 를 쓴다.
    """
    client = get_client(db_path if db_path is not None else db_path_for(collection_name))
    col = client.get_collection(collection_name)
    total = col.count()
    if total == 0:
        return {"collection": collection_name, "count": 0, "sampled": 0, "fields": {}}

    data = col.get(limit=min(sample_size, total), include=["metadatas"])
    n_sampled = len(data["metadatas"])
    field_types: dict[str, set[str]] = {}
    field_examples: dict[str, Any] = {}
    field_seen: Counter = Counter()
    for meta in data["metadatas"]:
        for key, value in meta.items():
            field_seen[key] += 1
            field_types.setdefault(key, set()).add(type(value).__name__)
            field_examples.setdefault(key, value)

    fields = {
        key: {
            "type": "|".join(sorted(types)),
            "coverage": f"{field_seen[key]}/{n_sampled}",
            "example": field_examples[key],
        }
        for key, types in sorted(field_types.items())
    }
    return {"collection": collection_name, "count": total, "sampled": n_sampled, "fields": fields}


def _print_schema(info: dict[str, Any]) -> None:
    print(f"컬렉션: {info['collection']}")
    print(f"총 레코드 수: {info['count']}")
    if info["count"] == 0:
        return
    print(f"(샘플 {info['sampled']}건 기준 메타데이터 필드 {len(info['fields'])}개)\n")
    for key, spec in info["fields"].items():
        print(f"  {key:<28} {spec['type']:<12} coverage={spec['coverage']:<10} 예시={spec['example']!r}")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ChromaDB 컬렉션 스키마 + 데이터 수 출력")
    p.add_argument("--collection", required=True, help="조회할 컬렉션명")
    p.add_argument("--db_path", type=Path, default=None,
                   help="ChromaDB 저장 경로(미지정 시 data/<collection>/)")
    p.add_argument("--sample_size", type=int, default=500, help="스키마 추론에 쓸 샘플 크기")
    p.add_argument("--json", action="store_true", dest="as_json", help="결과를 JSON으로 출력")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    info = inspect_schema(args.collection, args.db_path, args.sample_size)
    if args.as_json:
        print(json.dumps(info, ensure_ascii=False, indent=2, default=str))
    else:
        _print_schema(info)


if __name__ == "__main__":
    main()
