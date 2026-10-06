"""실험 기록 서버 — before/after 태깅 비교 (포트 8080).

python -m pikk_tagging.motion.RAFT_step.exp_server
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_repo_root = Path(__file__).resolve().parents[3]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

try:
    from flask import Flask, jsonify, send_file, abort
except ImportError:
    raise SystemExit("pip install flask")

from analysis.pikk_tagging.motion.RAFT_step.smooth import (
    detect_spikes, _interp_stats, classify_stats,
    _rolling_sum_stats, temporal_filter, smooth_and_classify,
)

_STEP_BASE  = Path(r"C:\Users\llm\workspace\outputs\pikk_output\RAFT_step_s5")
_STEP10_BASE= Path(r"C:\Users\llm\workspace\outputs\pikk_output\RAFT_step")
_CUT_BASE   = Path(r"C:\Users\llm\workspace\outputs\pikk_output\RAFT")
_VIDEO_BASE = Path(r"C:\Users\llm\workspace\outputs\pikk_output\motion_test")
_DOCS       = Path(__file__).parent.parent / "docs"

app = Flask(__name__)

_EXPS: dict[str, dict] = {
    "exp_cut": {
        "video_id": "2qkZ-FGbx-Q",
        "title": "컷 기반 분석",
        "before_label": "컷 기반 (1 레이블/shot)",
        "after_label":  "step=5 최종 결과",
    },
    "exp_s10": {
        "video_id": "KccntjIMKQI",
        "title": "step=10 분석",
        "before_label": "step=10 (0.4s 간격)",
        "after_label":  "step=5 (0.2s 간격)",
    },
    "exp01": {
        "video_id": "2qkZ-FGbx-Q",
        "title": "분류기 우선순위 버그",
        "before_label": "rotation 우선 (버그)",
        "after_label":  "zoom > pan > rotation",
    },
    "exp02": {
        "video_id": "KccntjIMKQI",
        "title": "샘플링 간격 단축",
        "before_label": "step=10 (0.4 s)",
        "after_label":  "step=5 (0.2 s)",
    },
    "exp03": {
        "video_id": "81HnwNayElo",
        "title": "누적 fallback 분류",
        "before_label": "단일 스텝 분류",
        "after_label":  "acc_window=9 fallback",
    },
    "exp04": {
        "video_id": "-5lAx7309cE",
        "title": "스파이크 제거",
        "before_label": "스파이크 미처리",
        "after_label":  "스파이크 보간",
    },
    "exp05": {
        "video_id": "5Qr07Yobj_4",
        "title": "rolling sum pan/rotation 오탐 제거",
        "before_label": "rolling sum 전체 승격 (pan/rotation 포함)",
        "after_label":  "zoom-only 승격 (pan/rotation 오탐 차단)",
    },
}


def _load(video_id: str) -> dict:
    return json.loads((_STEP_BASE / video_id / "step_results.json").read_text("utf-8"))


def _row(p: dict, label: str) -> dict[str, Any]:
    return {
        "frame_a": p["frame_a"], "frame_b": p["frame_b"],
        "time_a":  p["time_a"],  "time_b":  p["time_b"],
        "label": label, "is_spike": p.get("is_spike", False),
        "stats": p.get("stats", {}),
    }


def _old_classify(stats: dict) -> str:
    """rotation 우선 체크 버그 재현."""
    mag = stats["mean_mag"]
    if mag < 3.0:
        return "static"
    zoom  = stats["zoom_score"]
    pan_x = abs(stats["pan_x"]); pan_y = abs(stats["pan_y"])
    rot   = abs(stats["rotation_score"])
    if rot > 0.015:
        return "rotate_cw" if stats["rotation_score"] > 0 else "rotate_ccw"
    if abs(zoom) > 0.05:
        return "zoom_in" if zoom > 0 else "zoom_out"
    if pan_x > 5.0 or pan_y > 5.0:
        if pan_x >= pan_y:
            return "pan_right" if stats["pan_x"] > 0 else "pan_left"
        return "tilt_down" if stats["pan_y"] > 0 else "tilt_up"
    return "motion"


_CUT_LMAP = {"pan_up": "tilt_up", "pan_down": "tilt_down", "rotate": "rotate_cw"}


def _build_exp_cut() -> dict:
    vid = "2qkZ-FGbx-Q"
    ms  = json.loads((_CUT_BASE / vid / "motion_summary.json").read_text("utf-8"))
    fps = ms["fps"]
    before: list[dict] = []
    for s in ms["shots"]:
        lbl = _CUT_LMAP.get(s["motion_type"], s["motion_type"])
        st  = s.get("stats", {})
        for fa in range(s["start_frame"], s["end_frame"], 5):
            fb = min(fa + 5, s["end_frame"])
            before.append({"frame_a": fa, "frame_b": fb,
                "time_a": round(fa / fps, 2), "time_b": round(fb / fps, 2),
                "label": lbl, "is_spike": False, "stats": st})
    data  = _load(vid)
    after = smooth_and_classify(data["pairs"], step=data["step"], min_frames=10, acc_window=9)
    cfg   = _EXPS["exp_cut"]
    return {"video_id": vid, "fps": fps, "step_before": 5, "step_after": 5,
            "before_label": cfg["before_label"], "after_label": cfg["after_label"],
            "before": before, "after": after}


def _build_exp_s10() -> dict:
    vid    = "KccntjIMKQI"
    data10 = json.loads((_STEP10_BASE / vid / "step_results.json").read_text("utf-8"))
    data5  = _load(vid)
    fps    = data10["fps"]
    before = smooth_and_classify(data10["pairs"], step=10, min_frames=10, acc_window=9)
    after  = smooth_and_classify(data5["pairs"],  step=5,  min_frames=10, acc_window=9)
    cfg    = _EXPS["exp_s10"]
    return {"video_id": vid, "fps": fps, "step_before": 10, "step_after": 5,
            "before_label": cfg["before_label"], "after_label": cfg["after_label"],
            "before": before, "after": after}


def _build(exp_id: str) -> dict:
    cfg = _EXPS[exp_id]
    vid = cfg["video_id"]
    data = _load(vid)
    pairs, step, fps = data["pairs"], data["step"], data["fps"]
    spikes   = detect_spikes(pairs)
    smoothed = _interp_stats(pairs, spikes)

    if exp_id == "exp01":
        b_lbls = [_old_classify(p["stats"]) for p in smoothed]
        b_lbls = temporal_filter(b_lbls, step=step, min_frames=10)
        before = [_row(p, l) for p, l in zip(smoothed, b_lbls)]
        after  = smooth_and_classify(pairs, step=step, min_frames=10, acc_window=9)
        step_b = step_a = step

    elif exp_id == "exp02":
        pairs10 = [p for i, p in enumerate(pairs) if i % 2 == 0]
        before  = smooth_and_classify(pairs10, step=10, min_frames=10, acc_window=9)
        after   = smooth_and_classify(pairs,   step=step, min_frames=10, acc_window=9)
        step_b, step_a = 10, step

    elif exp_id == "exp03":
        b_lbls = [classify_stats(p["stats"]) for p in smoothed]
        b_lbls = temporal_filter(b_lbls, step=step, min_frames=10)
        before = [_row(p, l) for p, l in zip(smoothed, b_lbls)]
        after  = smooth_and_classify(pairs, step=step, min_frames=10, acc_window=9)
        step_b = step_a = step

    else:  # exp04
        b_lbls = [classify_stats(p["stats"]) for p in pairs]
        b_lbls = temporal_filter(b_lbls, step=step, min_frames=10)
        before = [_row(p, l) for p, l in zip(pairs, b_lbls)]
        after  = smooth_and_classify(pairs, step=step, min_frames=10, acc_window=9)
        step_b = step_a = step

    return {
        "video_id":    vid,
        "fps":         fps,
        "step_before": step_b,
        "step_after":  step_a,
        "before_label": cfg["before_label"],
        "after_label":  cfg["after_label"],
        "before": before,
        "after":  after,
    }


def _build_exp05() -> dict:
    """rolling sum 전체 승격(구버전) vs zoom-only 승격(현재) 비교."""
    vid = "5Qr07Yobj_4"
    data = _load(vid)
    pairs, step, fps = data["pairs"], data["step"], data["fps"]

    # Before: pan/rotation도 acc로 승격하던 구버전 재현
    spikes   = detect_spikes(pairs)
    smoothed = _interp_stats(pairs, spikes)
    acc_s    = _rolling_sum_stats(smoothed, window=9)
    b_lbls: list[str] = []
    for p, acc in zip(smoothed, acc_s):
        lbl = classify_stats(p["stats"])
        if lbl in ("static", "motion"):
            acc_lbl = classify_stats(acc)
            if acc_lbl not in ("static", "motion"):
                lbl = acc_lbl
        b_lbls.append(lbl)
    b_lbls = temporal_filter(b_lbls, step=step, min_frames=10)
    before = [_row(p, l) for p, l in zip(smoothed, b_lbls)]

    after = smooth_and_classify(pairs, step=step, min_frames=10, acc_window=9)
    cfg   = _EXPS["exp05"]
    return {
        "video_id": vid, "fps": fps, "step_before": step, "step_after": step,
        "before_label": cfg["before_label"], "after_label": cfg["after_label"],
        "before": before, "after": after,
    }


_EXTRA_BUILDERS = {
    "exp_cut": _build_exp_cut,
    "exp_s10": _build_exp_s10,
    "exp05":   _build_exp05,
}
_CACHE: dict[str, dict] = {}


@app.get("/")
def index():
    return send_file(_DOCS / "experiment_log.html")


@app.get("/api/exp/<exp_id>")
def api_exp(exp_id: str):
    if exp_id not in _EXPS:
        return jsonify({"error": "not found"}), 404
    if exp_id not in _CACHE:
        if exp_id in _EXTRA_BUILDERS:
            _CACHE[exp_id] = _EXTRA_BUILDERS[exp_id]()
        else:
            _CACHE[exp_id] = _build(exp_id)
    return jsonify(_CACHE[exp_id])


@app.get("/media/<video_id>")
def media(video_id: str):
    p = _VIDEO_BASE / video_id / f"{video_id}.mp4"
    if not p.exists():
        abort(404)
    return send_file(p, mimetype="video/mp4", conditional=True)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    print(f"실험 기록 서버: http://0.0.0.0:{args.port}")
    app.run(host="0.0.0.0", port=args.port, debug=False)


if __name__ == "__main__":
    main()
