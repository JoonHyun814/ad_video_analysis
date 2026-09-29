"""RAFT_step CLI — step 간격 dense flow, raw stats 저장.

사용법:
  python -m pikk_tagging.RAFT_step.cli --video path/to/video.mp4
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

_DEFAULT_OUT = Path(r"C:\Users\llm\workspace\outputs\pikk_output\RAFT_step")


def _save_flow_viz(results: list, viz_dir: Path) -> None:
    from .flow_viz import flow_to_image
    viz_dir.mkdir(parents=True, exist_ok=True)
    for r in results:
        if r.flow is None:
            continue
        fname = f"flow_{r.frame_a:05d}_{r.frame_b:05d}.png"
        viz = flow_to_image(r.flow)
        cv2.imwrite(str(viz_dir / fname),
                    cv2.cvtColor(viz, cv2.COLOR_RGB2BGR))


def _run(video_path: Path, out_dir: Path, args: argparse.Namespace) -> None:
    from .raft_flow import load_model, analyze_by_step

    out_dir.mkdir(parents=True, exist_ok=True)

    _log(f"[RAFT_step] 모델 로드 ({args.model_size}, {args.device})")
    model, transforms = load_model(args.device, args.model_size, args.model_dir)

    resize = None if args.no_resize else (640, 360)
    _log(f"[RAFT_step] 분석 시작: {video_path.name}  step={args.step}")
    results, fps, total = analyze_by_step(
        video_path, model, transforms, args.device, args.step, resize)

    if not results:
        _log("[RAFT_step] 결과 없음")
        return

    _save_flow_viz(results, out_dir / "flow_viz")

    pairs_out = []
    for r in results:
        pairs_out.append({
            "frame_a": r.frame_a, "frame_b": r.frame_b,
            "time_a":  r.time_a,  "time_b":  r.time_b,
            "flow_viz": f"flow_{r.frame_a:05d}_{r.frame_b:05d}.png"
                        if r.flow is not None else None,
            "stats": {
                "zoom_score":      round(r.stats.zoom_score, 6),
                "pan_x":           round(r.stats.pan_x, 4),
                "pan_y":           round(r.stats.pan_y, 4),
                "rotation_score":  round(r.stats.rotation_score, 6),
                "flow_var":        round(r.stats.flow_var, 4),
                "mean_mag":        round(r.stats.mean_mag, 4),
            },
        })

    summary = {
        "video":        str(video_path),
        "fps":          round(fps, 3),
        "step":         args.step,
        "total_frames": total,
        "total_pairs":  len(results),
        "pairs":        pairs_out,
    }
    (out_dir / "step_results.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"[RAFT_step] 저장 완료 → {out_dir}  ({len(results)}쌍)")


def main() -> None:
    parser = argparse.ArgumentParser(description="RAFT_step — step 간격 raw flow stats")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", metavar="URL")
    src.add_argument("--video", type=Path, metavar="PATH")
    parser.add_argument("--out-dir", type=Path, default=_DEFAULT_OUT)
    parser.add_argument("--step", type=int, default=10)
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--model-size", dest="model_size", default="large",
                        choices=["large", "small"])
    parser.add_argument("--no-resize", dest="no_resize", action="store_true")
    parser.add_argument("--model-dir", dest="model_dir", default=None)
    parser.add_argument("--cookies", type=Path, default=None)
    parser.add_argument("--cookies-from-browser", dest="cookies_from_browser", default=None)
    parser.add_argument("--js-runtimes", dest="js_runtimes", nargs="+", default=None)
    parser.add_argument("--remote-components", dest="remote_components", nargs="+", default=None)
    args = parser.parse_args()

    if args.url:
        from .download_video import download_video, video_id_from_url
        vid_id = video_id_from_url(args.url)
        vid_dir = args.out_dir / vid_id
        video_path = download_video(
            args.url, vid_dir,
            cookies=args.cookies,
            cookies_from_browser=args.cookies_from_browser,
            js_runtimes=args.js_runtimes,
            remote_components=args.remote_components,
        )
    else:
        video_path = args.video
        vid_dir = args.out_dir / video_path.stem

    _run(video_path, vid_dir, args)


def _log(msg: str) -> None:
    sys.stdout.buffer.write((msg + "\n").encode("utf-8", errors="replace"))
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
