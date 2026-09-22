"""Build a canonical tag tree from the tags table in stills_pikk.sql."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

TAG_ROW = re.compile(
    r"^\s*\((\d+),\s*'(mood|visual)',\s*'((?:\\.|[^'\\])*)',\s*'((?:\\.|[^'\\])*)',\s*'((?:\\.|[^'\\])*)',\s*(NULL|\d+),\s*(\d+)\),?"
)


def sql_unescape(value: str) -> str:
    return value.replace("\\'", "'").replace('\\"', '"').replace('\\\\', '\\')


def parse_tags(sql_path: Path) -> list[dict]:
    rows = []
    in_tags_insert = False
    with sql_path.open("r", encoding="utf-8", errors="replace") as source:
        for line in source:
            if line.startswith("INSERT INTO `tags`"):
                in_tags_insert = True
                continue
            if in_tags_insert and line.startswith("INSERT INTO ") and "`tags`" not in line:
                in_tags_insert = False
            if not in_tags_insert:
                continue
            match = TAG_ROW.match(line)
            if not match:
                continue
            tag_id, tag_type, raw, norm, base, canonical, usage = match.groups()
            rows.append({
                "tag_id": int(tag_id),
                "tag_type": tag_type,
                "raw_name": sql_unescape(raw),
                "norm_name": sql_unescape(norm),
                "base_name": sql_unescape(base),
                "canonical_tag_id": None if canonical == "NULL" else int(canonical),
                "usage_count": int(usage),
            })
    return rows


def build_tree(rows: list[dict]) -> dict:
    by_id = {row["tag_id"]: row for row in rows}
    children: dict[int, list[dict]] = {}
    for row in rows:
        parent = row["canonical_tag_id"]
        if parent is not None and parent != row["tag_id"] and parent in by_id:
            children.setdefault(parent, []).append(row)

    roots = []
    for tag_type in ("mood", "visual"):
        canonical = [row for row in rows if row["tag_type"] == tag_type and row["canonical_tag_id"] == row["tag_id"]]
        canonical.sort(key=lambda row: (-row["usage_count"], row["raw_name"]))
        nodes = []
        for row in canonical:
            variants = sorted(children.get(row["tag_id"], []), key=lambda item: (-item["usage_count"], item["raw_name"]))
            nodes.append({"tag": row, "children": variants})
        roots.append({"name": tag_type, "tag_count": sum(row["tag_type"] == tag_type for row in rows), "children": nodes})
    return {"name": "all_tags", "tag_count": len(rows), "children": roots}


def write_outputs(tree: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "pikk_tag_tree.json").write_text(json.dumps(tree, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Pikk 전체 태그 트리", "", f"총 태그 수: {tree['tag_count']:,}", "", "DB의 `canonical_tag_id` 관계를 기준으로 대표 태그와 변형 태그를 계층화했습니다.", ""]
    for group in tree["children"]:
        lines.append(f"- {group['name']} ({group['tag_count']:,})")
        for node in group["children"]:
            tag = node["tag"]
            lines.append(f"  - {tag['raw_name']} (id={tag['tag_id']}, usage={tag['usage_count']:,})")
            for variant in node["children"]:
                lines.append(f"    - {variant['raw_name']} (id={variant['tag_id']}, usage={variant['usage_count']:,})")
    (output_dir / "pikk_tag_tree.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sql", type=Path, default=Path("stills_pikk.sql"))
    parser.add_argument("--out-dir", type=Path, default=Path("output/pikk_output"))
    args = parser.parse_args()
    rows = parse_tags(args.sql)
    tree = build_tree(rows)
    write_outputs(tree, args.out_dir)
    print(f"Extracted {len(rows):,} tags")
    print(args.out_dir / "pikk_tag_tree.json")
    print(args.out_dir / "pikk_tag_tree.md")


if __name__ == "__main__":
    main()
