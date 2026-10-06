from utils.env_loader import get_data_root
"""샷 사이즈 실험 기록 뷰어 (Flask, 포트 8084).

EXP 01: 얼굴 감지만 사용 vs 얼굴 + edge fallback

python -m pikk_tagging.shot_size.exp_server
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

from analysis.pikk_tagging.shot_size.analyzer import analyze_video
from analysis.pikk_tagging.shot_size.classifier import temporal_smooth

_BASE    = get_data_root() / "pikk_output\shot_size"
_DOCS    = Path(__file__).parent / "docs"
_EXP_HTML = _DOCS / "experiment_log.html"
app      = Flask(__name__)


def _video_ids() -> list[str]:
    return sorted({rp.parent.name for rp in _BASE.glob("*/*/shot_size_results.json")})


def _build_exp01(video_id: str) -> dict:
    """EXP 01: face-only vs face+edge 비교."""
    rp = next(_BASE.glob(f"*/{video_id}/shot_size_results.json"), None)
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
        "before":   {"method": "face_only",       "frames": before, "dist": dist(before)},
        "after":    {"method": "face+edge_fallback", "frames": after,  "dist": dist(after)},
    }


@app.get("/")
def index():
    html = _EXP_HTML.read_text(encoding="utf-8") if _EXP_HTML.exists() else "<h1>experiment_log.html 없음</h1>"
    return Response(html, mimetype="text/html")


@app.get("/media/<video_id>")
def media(video_id: str):
    for rp in _BASE.glob(f"*/{video_id}/shot_size_results.json"):
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
    parser = argparse.ArgumentParser(description="샷 사이즈 실험 뷰어")
    parser.add_argument("--port", type=int, default=8084)
    args = parser.parse_args()
    print(f"실험 뷰어: http://localhost:{args.port}")
    app.run(host="0.0.0.0", port=args.port, debug=False)


if __name__ == "__main__":
    main()
