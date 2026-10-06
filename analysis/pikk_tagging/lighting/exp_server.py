from utils.env_loader import get_data_root
"""조명 실험 기록 서버 (Flask, 포트 8081).

experiment_log.html 을 서빙하고 before/after 비교 API를 제공한다.
  before: classify_frame_simple (mean_brightness 단독)
  after:  classify_frame (공간 분석 + backlight 감지)

python -m pikk_tagging.lighting.exp_server
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

try:
    from flask import Flask, Response, jsonify, send_file, abort
except ImportError:
    raise SystemExit("pip install flask")

from analysis.pikk_tagging.lighting.classifier import temporal_smooth
from analysis.pikk_tagging.lighting.io import load_results

_BASE = get_data_root() / "pikk_output\lighting"
_DOCS = Path(__file__).parent / "docs"

app = Flask(__name__)

_EXPS: dict[str, dict] = {
    "exp01": {
        "title": "공간 분석 없이 vs backlight 감지 추가",
        "before_label": "mean_brightness 단독 분류",
        "after_label":  "공간 분석 + backlight 감지",
    },
}


def _load(video_id: str) -> dict:
    return load_results(_BASE / video_id)


def _build_exp01(video_id: str) -> dict[str, Any]:
    """simple 분류(before) vs 공간 분석(after) 비교."""
    data   = _load(video_id)
    frames = data["frames"]
    step   = data["step"]

    before = temporal_smooth(frames, step=step, min_frames=30, simple=True)
    after  = temporal_smooth(frames, step=step, min_frames=30, simple=False)
    cfg    = _EXPS["exp01"]

    return {
        "video_id":     video_id,
        "fps":          data["fps"],
        "step":         step,
        "before_label": cfg["before_label"],
        "after_label":  cfg["after_label"],
        "before":       before,
        "after":        after,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def index():
    html_path = _DOCS / "experiment_log.html"
    if not html_path.exists():
        return Response("<h1>experiment_log.html 없음</h1>", mimetype="text/html")
    return Response(html_path.read_text(encoding="utf-8"), mimetype="text/html")


@app.get("/media/<video_id>")
def media(video_id: str):
    rp = _BASE / video_id / "lighting_results.json"
    if not rp.exists():
        abort(404)
    data = json.loads(rp.read_text(encoding="utf-8"))
    path = Path(data.get("video", ""))
    if not path.exists():
        abort(404)
    return send_file(path, mimetype="video/mp4", conditional=True)


@app.get("/api/videos")
def api_videos():
    return jsonify([p.parent.name for p in sorted(_BASE.glob("*/lighting_results.json"))])


@app.get("/api/exp01/<video_id>")
def api_exp01(video_id: str):
    rp = _BASE / video_id / "lighting_results.json"
    if not rp.exists():
        return jsonify({"error": "data not found"}), 404
    try:
        return jsonify(_build_exp01(video_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="조명 실험 기록 서버")
    parser.add_argument("--port", type=int, default=8081)
    args = parser.parse_args()
    print(f"실험 기록 서버 시작: http://localhost:{args.port}")
    app.run(host="0.0.0.0", port=args.port, debug=False)


if __name__ == "__main__":
    main()
