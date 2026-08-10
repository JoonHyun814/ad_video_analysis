#!/usr/bin/env python3
"""Normalize storyboard image assets and make HTML slots follow their ratios.

The tool intentionally uses only Python's standard library plus ffmpeg/ffprobe.
Codex can create a small JSON manifest, run this tool, and then render the HTML.

Copied verbatim (not imported) from C:\\Analysis_workspace\\ad_video_analysis\\story_board\\
storyboard_image_layout.py into this pipeline so retrieval_pipeline has no dependency on
that separate project (user request). Logic is unchanged — categories "character",
"character-detail", "product", "product-use", "environment", "storyboard", "lighting" cover
the slot kinds produced by storyboard_template.py (character front/profile -> character,
character costume close-up -> character-detail, product shots/logo -> product, environment
-> environment, per-cut keyframes -> storyboard).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


PRESETS = {
    "character": (4, 5),
    "character-detail": (4, 5),
    "product": (1, 1),
    "product-use": (1, 1),
    "environment": (1, 1),
    "storyboard": (6, 5),
    "lighting": (1, 1),
    "default": (6, 5),
}

STYLE_ID = "storyboard-adaptive-image-layout"
STYLE = f"""
  /* Added by storyboard_image_layout.py */
  #{STYLE_ID} {{}}
  .slot.has-image {{
    padding: 0;
    min-height: 0;
    aspect-ratio: var(--storyboard-image-ratio, 6 / 5);
    overflow: hidden;
    border-style: solid;
    background: #e9e9e5;
    position: relative;
  }}
  .slot.has-image img {{
    display: block;
    width: 100%;
    height: 100%;
    min-height: 0;
    object-fit: cover;
    object-position: center;
  }}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create no-crop storyboard assets and adaptive HTML image slots."
    )
    parser.add_argument("--html", required=True, type=Path, help="Completed HTML to update")
    parser.add_argument(
        "--manifest",
        type=Path,
        help=(
            "JSON manifest. Each asset needs output and category; source is optional. "
            "Paths are relative to the manifest directory."
        ),
    )
    parser.add_argument(
        "--output-html",
        type=Path,
        help="Write to a new HTML path instead of updating --html",
    )
    parser.add_argument("--report", type=Path, help="Optional JSON validation report")
    parser.add_argument("--width", type=int, default=1200, help="Output asset width")
    parser.add_argument(
        "--no-assets",
        action="store_true",
        help="Only update HTML ratios; do not rebuild raster assets",
    )
    return parser.parse_args()


def resolve_tool(name: str) -> str:
    found = shutil.which(name)
    if not found:
        raise RuntimeError(f"Required executable not found on PATH: {name}")
    return found


def load_manifest(path: Path | None) -> tuple[Path, list[dict[str, object]]]:
    if path is None:
        return Path.cwd(), []
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(data, dict):
        assets = data.get("assets")
    else:
        assets = data
    if not isinstance(assets, list):
        raise ValueError("Manifest must be an array or an object with an 'assets' array")
    return path.resolve().parent, assets


def normalized_ratio(category: str) -> tuple[int, int]:
    return PRESETS.get(category, PRESETS["default"])


def build_asset(
    ffmpeg: str,
    source: Path,
    output: Path,
    ratio: tuple[int, int],
    width: int,
) -> None:
    rw, rh = ratio
    height = round(width * rh / rw)
    height += height % 2
    safe_w = round(width * 0.92)
    safe_h = round(height * 0.92)
    safe_w -= safe_w % 2
    safe_h -= safe_h % 2
    filter_graph = (
        f"color=c=0x111318:s={width}x{height}[bg];"
        f"[0:v]scale={safe_w}:{safe_h}:force_original_aspect_ratio=decrease[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[out]"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-filter_complex",
        filter_graph,
        "-map",
        "[out]",
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(output),
    ]
    subprocess.run(command, check=True)


def update_slot_markup(html: str, asset: dict[str, object], ratio: tuple[int, int]) -> tuple[str, int]:
    output = str(asset["output"]).replace("\\", "/")
    match_value = asset.get("html_src", output)
    src = re.escape(str(match_value).replace("\\", "/"))
    pattern = re.compile(
        rf'(<div\b(?=[^>]*\bclass="[^"]*\bslot\b[^"]*\bhas-image\b[^"]*")[^>]*?)>'
        rf'(?=\s*<img\b[^>]*\bsrc="{src}")',
        flags=re.IGNORECASE,
    )
    rw, rh = ratio

    def replace(match: re.Match[str]) -> str:
        opening = match.group(1)
        style_match = re.search(r'\sstyle="([^"]*)"', opening, flags=re.IGNORECASE)
        declaration = f"--storyboard-image-ratio: {rw} / {rh};"
        if style_match:
            existing = re.sub(
                r"--storyboard-image-ratio\s*:[^;]+;?",
                "",
                style_match.group(1),
                flags=re.IGNORECASE,
            ).strip()
            value = f"{existing.rstrip(';')}; {declaration}" if existing else declaration
            opening = (
                opening[: style_match.start()]
                + f' style="{value}"'
                + opening[style_match.end() :]
            )
        else:
            opening += f' style="{declaration}"'
        return opening + ">"

    return pattern.subn(replace, html, count=1)


def inject_style(html: str) -> str:
    previous = re.compile(
        rf"\s*<style\b[^>]*\bid=[\"']{STYLE_ID}[\"'][^>]*>.*?</style>",
        flags=re.IGNORECASE | re.DOTALL,
    )
    html = previous.sub("", html)
    block = f'\n<style id="{STYLE_ID}">{STYLE}</style>\n'
    if re.search(r"</head>", html, flags=re.IGNORECASE):
        return re.sub(r"</head>", block + "</head>", html, count=1, flags=re.IGNORECASE)
    return block + html


def main() -> int:
    args = parse_args()
    html_path = args.html.resolve()
    output_html = (args.output_html or args.html).resolve()
    manifest_root, assets = load_manifest(args.manifest)
    html = html_path.read_text(encoding="utf-8-sig")
    ffmpeg = None if args.no_assets else resolve_tool("ffmpeg")
    results: list[dict[str, object]] = []

    for index, asset in enumerate(assets, start=1):
        if not isinstance(asset, dict) or "output" not in asset:
            raise ValueError(f"Manifest asset #{index} needs an output path")
        category = str(asset.get("category", "default"))
        ratio = normalized_ratio(category)
        output = (manifest_root / str(asset["output"])).resolve()
        source_value = asset.get("source")
        rebuilt = False
        if source_value and not args.no_assets:
            source = (manifest_root / str(source_value)).resolve()
            if not source.is_file():
                raise FileNotFoundError(f"Source asset does not exist: {source}")
            build_asset(ffmpeg, source, output, ratio, args.width)
            rebuilt = True
        html, count = update_slot_markup(html, asset, ratio)
        results.append(
            {
                "output": str(output),
                "category": category,
                "ratio": f"{ratio[0]}:{ratio[1]}",
                "rebuilt": rebuilt,
                "html_slots_updated": count,
            }
        )

    html = inject_style(html)
    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_html.write_text(html, encoding="utf-8")
    report = {
        "html": str(output_html),
        "asset_count": len(results),
        "updated_slot_count": sum(int(item["html_slots_updated"]) for item in results),
        "assets": results,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if assets and report["updated_slot_count"] != len(results):
        print("Not every manifest asset matched an HTML slot.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
