"""Extract YouTube video metadata from a stills_pikk SQL dump.

This module only reads the SQL dump and writes a metadata catalog.  It never
downloads video files or contacts YouTube.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


_FIELD_PATTERNS = {
    "pikk_video_id": re.compile(r'"id":(\d+),"video_id":"([^"]+)"'),
    "preview_url": re.compile(r'"preview_url":"([^"]+)"'),
    "video_title": re.compile(r'"video_title":"((?:\\.|[^"\\])*)"'),
    "duration_seconds": re.compile(r'"video_duration":(\d+)'),
    "thumbnail_url": re.compile(r'"video_thumbnail":"([^"]+)"'),
    "sample_timestamp_seconds": re.compile(r'"timestamp_seconds":(\d+)'),
}


def _json_unescape(value: str) -> str:
    """Decode a JSON string fragment without depending on SQL text encoding."""
    try:
        return json.loads(f'"{value}"')
    except json.JSONDecodeError:
        return value.replace("\\'", "'").replace('\\"', '"').replace("\\\\", "\\")


def extract_video_catalog(sql_path: Path) -> list[dict]:
    """Return unique videos found in ``scene_raw`` payload rows."""
    by_youtube_id: dict[str, dict] = {}
    with sql_path.open("r", encoding="utf-8", errors="replace") as source:
        for line_number, line in enumerate(source, 1):
            id_match = _FIELD_PATTERNS["pikk_video_id"].search(line)
            if not id_match:
                continue

            pikk_video_id, youtube_id = id_match.groups()
            preview = _FIELD_PATTERNS["preview_url"].search(line)
            if preview is None:
                continue

            def field(name: str) -> str | None:
                match = _FIELD_PATTERNS[name].search(line)
                return match.group(1) if match else None

            title_fragment = field("video_title")
            record = {
                "pikk_video_id": int(pikk_video_id),
                "youtube_id": youtube_id,
                "youtube_url": f"https://www.youtube.com/watch?v={youtube_id}",
                "preview_url": preview.group(1),
                "video_title": _json_unescape(title_fragment) if title_fragment else None,
                "duration_seconds": int(field("duration_seconds")) if field("duration_seconds") else None,
                "thumbnail_url": field("thumbnail_url"),
                "sample_timestamp_seconds": int(field("sample_timestamp_seconds")) if field("sample_timestamp_seconds") else None,
                "sql_line_number": line_number,
            }
            by_youtube_id.setdefault(youtube_id, record)

    return sorted(by_youtube_id.values(), key=lambda item: item["pikk_video_id"])


def write_catalog(records: list[dict], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "pikk_video_catalog.json"
    csv_path = output_dir / "pikk_video_catalog.csv"
    json_path.write_text(
        json.dumps({"video_count": len(records), "videos": records}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with csv_path.open("w", newline="", encoding="utf-8-sig") as destination:
        writer = csv.DictWriter(destination, fieldnames=list(records[0]) if records else ["pikk_video_id"])
        writer.writeheader()
        writer.writerows(records)
    return json_path, csv_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract Pikk video IDs and URLs from an SQL dump")
    parser.add_argument("--sql", type=Path, default=Path("stills_pikk.sql"))
    parser.add_argument("--out-dir", type=Path, default=Path("output/pikk_output"))
    args = parser.parse_args()
    records = extract_video_catalog(args.sql)
    json_path, csv_path = write_catalog(records, args.out_dir)
    print(f"Extracted {len(records):,} videos")
    print(json_path)
    print(csv_path)


if __name__ == "__main__":
    main()

