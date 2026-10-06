from utils.env_loader import get_data_root
"""포커스 실험 기록 뷰어 (Flask, 포트 8085).

EXP 01: global_sharpness 만 사용 vs center/bg ratio + rack focus 감지

python -m pikk_tagging.focus.exp_server
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

try:
    from flask import Flask, Response, jsonify, send_file, abort
except ImportError:
    raise SystemExit("pip install flask")

from analysis.pikk_tagging.focus.classifier import temporal_smooth

_BASE     = get_data_root() / "pikk_output\focus"
_DOCS     = Path(__file__).parent / "docs"
_EXP_HTML = _DOCS / "experiment_log.html"
app       = Flask(__name__)


def _video_ids() -> list[str]:
    return sorted({rp.parent.name for rp in _BASE.glob("*/*/focus_results.json")})


def _build_exp01(video_id: str) -> dict:
    """EXP 01: global_sharpness 단순 분류 vs center/bg+rack_focus 전체 분류."""
    rp = next(_BASE.glob(f"*/{video_id}/focus_results.json"), None)
    if rp is None:
        return {"error": "not found"}
    data   = json.loads(rp.read_text(encoding="utf-8"))
    frames = data["frames"]
    step   = data.get("step", 30)

    before = temporal_smooth(frames, step=step, min_frames=step, simple=True)
    after  = temporal_smooth(frames, step=step, min_frames=step, simple=False)

    def dist(labeled):
        from collections import Counter
        c = Counter(f["label"] for f in labeled)
        return dict(c.most_common())

    return {
        "video_id": video_id,
        "before":   {"method": "global_sharpness_only",        "frames": before, "dist": dist(before)},
        "after":    {"method": "center_bg_ratio+rack_focus",   "frames": after,  "dist": dist(after)},
    }


@app.get("/")
def index():
    html = _EXP_HTML.read_text(encoding="utf-8") if _EXP_HTML.exists() else "<h1>experiment_log.html 없음</h1>"
    return Response(html, mimetype="text/html")


@app.get("/media/<video_id>")
def media(video_id: str):
    for rp in _BASE.glob(f"*/{video_id}/focus_results.json"):
        data = json.loads(rp.read_text(encoding="utf-8"))
        path = Path(data.get("video", ""))
        if path.exists():
            return send_file(path, mimetype="video/mp4", conditional=True)
    abort(404)


@app.get("/api/videos")
def api_videos():
    return jsonify(_video_ids())


@app.get("/api/exp01/<video_id>")
def api_exp01(video_id: str):
    return jsonify(_build_exp01(video_id))


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="포커스 실험 뷰어")
    parser.add_argument("--port", type=int, default=8085)
    args = parser.parse_args()
    print(f"실험 뷰어: http://localhost:{args.port}")
    app.run(host="0.0.0.0", port=args.port, debug=False)


if __name__ == "__main__":
    main()
