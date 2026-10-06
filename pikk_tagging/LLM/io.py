"""VL 분석 결과 JSON 저장/로딩."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def save_results(result: dict[str, Any], out_dir: Path) -> Path:
    """결과를 out_dir/vl_results.json 에 저장하고 경로 반환."""
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "vl_results.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def load_results(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
