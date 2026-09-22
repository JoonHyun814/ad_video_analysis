"""영상별 분석 결과를 JSON으로 저장.

python -m pikk_tagging.optical_flow.save_analysis [--force]
"""
from __future__ import annotations

import json
from pathlib import Path

from .compare_multilabel import TEST_CASES, _find_video, _parse_gt_from_sql
from .shot_detect import detect_shots, find_shot_for_ts, extract_shot_frames
from .flow_utils import log
from . import farneback as fb_mod
from . import lucas_kanade as lk_mod
from ..OSH.feature_match import motion_for_shot as osh_motion_for_shot

_OUT_BASE = Path(r"C:\Users\llm\workspace\outputs\pikk_output\videos")


def analyze_video(
    video_id: str,
    ts: float,
    gt_labels: list[str],
    step_sec: float = 1.0,
) -> dict | None:
    """단일 영상 전체 샷 분석 → 결과 dict."""
    video_path = _find_video(video_id)
    if video_path is None:
        log(f"  [skip] {video_id} — 파일 없음")
        return None

    sql_labels = _parse_gt_from_sql(video_id)
    effective_gt = sql_labels if sql_labels else gt_labels

    shots, fps, total = detect_shots(video_path)
    step = max(1, int(step_sec * fps))

    gt_shot_idx = find_shot_for_ts(shots, ts, fps)
    if gt_shot_idx is None:
        gt_shot_idx = len(shots) - 1

    shot_results: list[dict] = []
    for i, (s, e) in enumerate(shots):
        frames = extract_shot_frames(video_path, s, e, step)
        if len(frames) < 2:
            osh = fb = lk = "too_short"
        else:
            osh = osh_motion_for_shot(frames)
            fb  = fb_mod.motion_for_shot(frames)
            lk  = lk_mod.motion_for_shot(frames)

        shot_results.append({
            "shot_idx": i,
            "start_frame": s,
            "end_frame": e,
            "start_sec": round(s / fps, 2),
            "end_sec": round(e / fps, 2),
            "duration_sec": round((e - s) / fps, 2),
            "is_gt_shot": (i == gt_shot_idx),
            "osh": osh,
            "fb": fb,
            "lk": lk,
        })
        log(f"  [{i+1}/{len(shots)}] fb={fb}  lk={lk}")

    gt_shot = shot_results[gt_shot_idx]
    return {
        "video_id": video_id,
        "fps": round(fps, 2),
        "total_frames": total,
        "duration_sec": round(total / fps, 2),
        "gt_labels": effective_gt,
        "gt_timestamp_sec": ts,
        "gt_shot_idx": gt_shot_idx,
        "dominant": {
            "osh": gt_shot["osh"],
            "fb":  gt_shot["fb"],
            "lk":  gt_shot["lk"],
        },
        "shots": shot_results,
    }


def save_result(result: dict) -> Path:
    out_dir = _OUT_BASE / result["video_id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "analysis.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="영상 분석 결과를 JSON으로 저장")
    parser.add_argument("--force", action="store_true", help="기존 결과 덮어쓰기")
    parser.add_argument("--step-sec", dest="step_sec", type=float, default=1.0)
    args = parser.parse_args()

    done = 0
    for vid, ts, gt_labels in TEST_CASES:
        out = _OUT_BASE / vid / "analysis.json"
        if out.exists() and not args.force:
            log(f"[skip] {vid} — 이미 분석됨")
            continue
        log(f"\n[{done+1}/{len(TEST_CASES)}] {vid}  ts={ts}s")
        result = analyze_video(vid, ts, gt_labels, step_sec=args.step_sec)
        if result:
            p = save_result(result)
            log(f"  saved → {p}")
            done += 1

    log(f"\n완료: {done}개 저장")


if __name__ == "__main__":
    main()
