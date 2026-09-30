"""focus_results.json 저장/로드."""
from __future__ import annotations

import json
from pathlib import Path


def save_results(result: dict, out_dir: str | Path) -> Path:
    """result dict → <out_dir>/focus_results.json"""
    out  = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "focus_results.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_results(out_dir: str | Path) -> dict:
    path = Path(out_dir) / "focus_results.json"
    return json.loads(path.read_text(encoding="utf-8"))
