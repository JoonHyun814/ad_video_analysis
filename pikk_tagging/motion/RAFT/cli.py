"""RAFT 광학 흐름 CLI.

컷 감지 → 샷 단위 RAFT (샷당 프레임 쌍 1개, 태그 1개).

사용법:
  python -m pikk_tagging.motion.RAFT.cli --url <YouTube/직접URL>
  python -m pikk_tagging.motion.RAFT.cli --video path/to/video.mp4
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

_DEFAULT_OUT = Path(r"C:\Users\llm\workspace\outputs\pikk_output\RAFT")


def _save_flow_viz(sr, viz_dir: Path) -> str | None:
    """샷 1개의 flow 시각화 저장 → 파일명 반환 (flow 없으면 None)."""
    if sr.flow is None:
        return None
    from .flow_viz import flow_to_image
    viz_dir.mkdir(parents=True, exist_ok=True)
    fname = f"shot_{sr.shot_idx:02d}_flow_{sr.frame_a:05d}_{sr.frame_b:05d}.png"
    viz = flow_to_image(sr.flow)
    cv2.imwrite(str(viz_dir / fname), cv2.cvtColor(viz, cv2.COLOR_RGB2BGR))
    return fname


def _run(video_path: Path, out_dir: Path, args: argparse.Namespace) -> None:
    from .raft_flow import load_model, analyze_by_shots

    out_dir.mkdir(parents=True, exist_ok=True)

    _log(f"[RAFT] 모델 로드 ({args.model_size}, {args.device}, dir={args.model_dir or '기본 캐시'})")
    model, transforms = load_model(args.device, args.model_size, args.model_dir)

    resize = None if args.no_resize else (640, 360)
    _log(f"[RAFT] 분석 시작 (컷 기반, 샷당 1쌍): {video_path.name}  step={args.step}")
    shot_results, fps = analyze_by_shots(video_path, model, transforms,
                                          args.device, args.step, resize)

    if not shot_results:
        _log("[RAFT] 분석 결과 없음")
        return

    viz_dir = out_dir / "flow_viz"
    flow_stats_rows: list[dict] = []
    shot_summaries: list[dict] = []

    for sr in shot_results:
        viz_fname = _save_flow_viz(sr, viz_dir)
        stats_dict = None
        if sr.stats is not None:
            stats_dict = {
                "zoom_score":     round(sr.stats.zoom_score, 6),
                "pan_x":          round(sr.stats.pan_x, 4),
                "pan_y":          round(sr.stats.pan_y, 4),
                "rotation_score": round(sr.stats.rotation_score, 6),
                "flow_var":       round(sr.stats.flow_var, 4),
                "mean_mag":       round(sr.stats.mean_mag, 4),
                "n_valid":        sr.stats.n_valid,
            }
            flow_stats_rows.append({
                "shot_idx": sr.shot_idx,
                "frame_a": sr.frame_a, "frame_b": sr.frame_b,
                "time_a": round(sr.frame_a / fps, 2),
                "time_b": round(sr.frame_b / fps, 2),
                "motion_type": sr.motion_type,
                "flow_viz": viz_fname,
                "stats": stats_dict,
            })

        shot_summaries.append({
            "shot_idx":       sr.shot_idx,
            "start_frame":    sr.start_frame, "end_frame":   sr.end_frame,
            "start_sec":      sr.start_sec,   "end_sec":     sr.end_sec,
            "duration_sec":   sr.duration_sec,
            "frame_a":        sr.frame_a,     "frame_b":     sr.frame_b,
            "motion_type":    sr.motion_type,
            "stats":          stats_dict,
        })

    (out_dir / "flow_stats.json").write_text(
        json.dumps(flow_stats_rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    summary = {
        "video":   str(video_path),
        "fps":     round(fps, 2),
        "n_shots": len(shot_results),
        "shots":   shot_summaries,
    }
    (out_dir / "motion_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    _log(f"[RAFT] 저장 완료 → {out_dir}")
    _log("[RAFT] 샷별 결과:")
    for ss in shot_summaries:
        mag_str = (f"  mag={ss['stats']['mean_mag']:.1f}px"
                   if ss["stats"] else "")
        _log(f"  shot {ss['shot_idx']:>2}  {ss['start_sec']:.1f}~{ss['end_sec']:.1f}s"
             f"  → {ss['motion_type']}{mag_str}")


def main() -> None:
    parser = argparse.ArgumentParser(description="RAFT 광학 흐름 분석 (컷 기반, 샷당 1쌍)")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", metavar="URL", help="영상 URL (YouTube 또는 직접 링크)")
    src.add_argument("--video", type=Path, metavar="PATH", help="로컬 영상 파일 경로")

    parser.add_argument("--out-dir", type=Path, default=_DEFAULT_OUT, metavar="DIR",
                        help=f"출력 루트 (기본: {_DEFAULT_OUT})")
    parser.add_argument("--step", type=int, default=25, metavar="N",
                        help="샷 내 두 프레임 사이 간격 (기본 25 = 1초@25fps)")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"],
                        help="추론 장치 (기본: cpu)")
    parser.add_argument("--model-size", dest="model_size", default="large",
                        choices=["large", "small"],
                        help="RAFT 모델 크기 (기본: large)")
    parser.add_argument("--no-resize", dest="no_resize", action="store_true",
                        help="프레임 리사이즈 생략 (고해상도에서 매우 느림)")
    parser.add_argument("--model-dir", dest="model_dir", default=None, metavar="DIR",
                        help="모델 weights 저장 경로 (기본: torch 캐시 ~/.cache/torch/hub)")
    # ── 쿠키 / YouTube 봇 우회 ────────────────────────────────────────────────
    parser.add_argument("--cookies", type=Path, default=None, metavar="FILE",
                        help="Netscape cookies.txt")
    parser.add_argument("--cookies-from-browser", dest="cookies_from_browser",
                        metavar="BROWSER", default=None,
                        help="브라우저 쿠키 직접 읽기 (chrome|edge|firefox)")
    parser.add_argument("--js-runtimes", dest="js_runtimes", nargs="+",
                        metavar="RUNTIME", default=None)
    parser.add_argument("--remote-components", dest="remote_components", nargs="+",
                        metavar="SPEC", default=None)
    args = parser.parse_args()

    if args.url:
        from .download_video import download_video, video_id_from_url
        vid_id = video_id_from_url(args.url)
        vid_dir = args.out_dir / vid_id
        _log(f"[RAFT] 다운로드: {args.url}")
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
