"""optical_flow CLI 진입점.

subcommands:
  video       영상 전체 모션 분석 (Farneback + LK 동시)
  compare     SQL 레이블 vs CV 감지 비교 (테스트 케이스 4개 고정)
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .flow_utils import video_meta, log
from . import farneback, lucas_kanade

# ── compare 모드 고정 테스트 케이스 ──────────────────────
_TEST_CASES = [
    {
        "video_id": "81HnwNayElo",
        "path": r"C:\Users\llm\workspace\outputs\pikk_output\motion_test\81HnwNayElo\81HnwNayElo.mp4",
        "ts": 24, "sql_tag": "슬로우 줌인 (Slow Push-in)", "expected": "zoom_in",
    },
    {
        "video_id": "DtQWxnQAwec",
        "path": r"C:\Users\llm\workspace\outputs\pikk_output\motion_test\DtQWxnQAwec\DtQWxnQAwec.mp4",
        "ts": 7, "sql_tag": "카메라 줌 아웃(Zoom-out) 연출", "expected": "zoom_out",
    },
    {
        "video_id": "7SDum-LuYZg",
        "path": r"C:\Users\llm\workspace\outputs\pikk_output\motion_test\7SDum-LuYZg\7SDum-LuYZg.mp4",
        "ts": 45, "sql_tag": "패닝 샷", "expected": "pan",
    },
    {
        "video_id": "IEd24npXNUI",
        "path": r"C:\Users\llm\workspace\outputs\pikk_output\motion_test\IEd24npXNUI\IEd24npXNUI.mp4",
        "ts": 22, "sql_tag": "클로즈업→풀샷 반전 줌아웃", "expected": "zoom_out",
    },
]


def _cmd_video(args: argparse.Namespace) -> None:
    video_path = args.video
    meta = video_meta(video_path)
    log(f"[optical_flow:video] {video_path.name}  fps={meta['fps']:.1f}  step={args.step}")

    fb_results = farneback.analyze_full_video(video_path, step=args.step)
    farneback.print_results(fb_results, video_path.name)

    lk_results = lucas_kanade.analyze_full_video(video_path, step=args.step)
    lucas_kanade.print_results(lk_results, video_path.name)


def _match(detected: str, expected: str) -> bool:
    """zoom_in/zoom_out는 방향 무관 zoom으로, pan_*는 pan으로 퉁친다."""
    if expected == "pan":
        return detected.startswith("pan")
    if "zoom" in expected:
        return "zoom" in detected
    return detected == expected


def _cmd_compare(args: argparse.Namespace) -> None:
    window_sec = args.window
    step_sec = args.step_sec

    log("=" * 76)
    log(f"{'video_id':<22} {'SQL 태그':<28} {'FB':>8} {'LK':>8} {'일치?':>10}")
    log("=" * 76)

    fb_correct = lk_correct = 0
    for case in _TEST_CASES:
        path = Path(case["path"])
        if not path.exists():
            log(f"  {case['video_id']}: 파일 없음 — skip")
            continue

        fb_dom, fb_res = farneback.analyze_window(path, case["ts"], window_sec, step_sec)
        lk_dom, lk_res = lucas_kanade.analyze_window(path, case["ts"], window_sec, step_sec)

        expected = case["expected"]
        fb_ok = _match(fb_dom, expected)
        lk_ok = _match(lk_dom, expected)
        if fb_ok: fb_correct += 1
        if lk_ok: lk_correct += 1

        fb_mark = "✓" if fb_ok else "✗"
        lk_mark = "✓" if lk_ok else "✗"
        log(f"{case['video_id']:<22} {case['sql_tag'][:26]:<28} {fb_dom:>8} {lk_dom:>8}  {fb_mark}FB {lk_mark}LK")

        # 상세 zoom score 추이
        fb_valid = [r for r in fb_res if r.motion_type != "cut"]
        lk_valid = [r for r in lk_res if r.motion_type != "cut"]
        fb_zoom = [round(r.stats.zoom_score, 5) for r in fb_valid]
        lk_zoom = [round(r.stats.zoom_score, 5) for r in lk_valid]
        log(f"  FB zoom: {fb_zoom}")
        log(f"  LK zoom: {lk_zoom}")
        log(f"  FB pan : {[round(r.stats.pan_x,2) for r in fb_valid]}")
        log("")

    n = len(_TEST_CASES)
    log("=" * 76)
    log(f"Farneback 정확도: {fb_correct}/{n}  |  LK 정확도: {lk_correct}/{n}")


def main() -> None:
    parser = argparse.ArgumentParser(description="optical_flow 카메라 모션 분석")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_vid = sub.add_parser("video", help="단일 영상 전체 분석")
    p_vid.add_argument("video", type=Path)
    p_vid.add_argument("--step", type=int, default=25, metavar="N",
                       help="프레임 샘플링 간격 (기본 25 ≈ 1초@25fps)")

    p_cmp = sub.add_parser("compare", help="SQL 레이블 vs CV 감지 비교")
    p_cmp.add_argument("--window", type=float, default=5.0, metavar="SEC",
                       help="타임스탬프 ±창 크기(초, 기본 5)")
    p_cmp.add_argument("--step-sec", dest="step_sec", type=float, default=1.0,
                       metavar="SEC", help="프레임 쌍 간격(초, 기본 1.0)")

    args = parser.parse_args()
    if args.cmd == "video":
        _cmd_video(args)
    else:
        _cmd_compare(args)


if __name__ == "__main__":
    main()
