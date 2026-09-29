"""GT / OSH / Farneback / LK 샷 단위 결과 비교.

python -m pikk_tagging.optical_flow.compare
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .shot_detect import detect_shots, shots_summary, find_shot_for_ts, extract_shot_frames
from .flow_utils import log
from . import farneback as fb_mod
from . import lucas_kanade as lk_mod
from ..OSH.feature_match import motion_for_shot as osh_motion_for_shot

_SQL_PATH = Path(r"C:\Users\llm\workspace\outputs\stills_pikk.sql")

TEST_CASES = [
    {"video_id": "81HnwNayElo", "ts": 24, "sql_tag": "슬로우 줌인 (Slow Push-in)",    "expected": "zoom_in",  "path": r"C:\Users\llm\workspace\outputs\pikk_output\motion_test\81HnwNayElo\81HnwNayElo.mp4"},
    {"video_id": "DtQWxnQAwec", "ts": 7,  "sql_tag": "카메라 줌 아웃(Zoom-out) 연출",  "expected": "zoom_out", "path": r"C:\Users\llm\workspace\outputs\pikk_output\motion_test\DtQWxnQAwec\DtQWxnQAwec.mp4"},
    {"video_id": "7SDum-LuYZg", "ts": 45, "sql_tag": "패닝 샷",                       "expected": "pan",      "path": r"C:\Users\llm\workspace\outputs\pikk_output\motion_test\7SDum-LuYZg\7SDum-LuYZg.mp4"},
    {"video_id": "IEd24npXNUI", "ts": 22, "sql_tag": "클로즈업→풀샷 반전 줌아웃",       "expected": "zoom_out", "path": r"C:\Users\llm\workspace\outputs\pikk_output\motion_test\IEd24npXNUI\IEd24npXNUI.mp4"},
]

# SQL visual_elements → 정규화된 모션 레이블
_GT_MAP: list[tuple[str, list[str]]] = [
    ("zoom_in",  ["줌인", "줌 인", "push-in", "push in", "slow push", "슬로우 줌"]),
    ("zoom_out", ["줌아웃", "줌 아웃", "zoom out", "zoom-out", "반전 줌아웃", "점진적 줌 아웃"]),
    ("pan",      ["패닝", "팬(", "팬 샷", "팬기법", "panning", "pan shot", "pan)"]),
    ("tilt",     ["틸트", "tilt up", "tilt down", "틸트업", "틸트다운"]),
    ("handheld", ["핸드헬드", "handheld"]),
    ("tracking", ["트래킹", "tracking"]),
]


def _parse_gt_from_sql(video_id: str) -> list[dict]:
    """SQL 파일에서 video_id 에 해당하는 stills 추출."""
    stills: list[dict] = []
    key = f'"video_id":"{video_id}"'
    with _SQL_PATH.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if key not in line:
                continue
            s = line.find("{")
            e = line.rfind("}")
            if s < 0 or e <= s:
                continue
            try:
                stills.append(json.loads(line[s : e + 1]))
            except Exception:
                pass
    return stills


def _normalize_motion(visual_elements: list[str]) -> str | None:
    """visual_elements 리스트에서 모션 레이블 추출."""
    joined = " ".join(visual_elements).lower()
    for label, keywords in _GT_MAP:
        if any(kw.lower() in joined for kw in keywords):
            return label
    return None


def _match(detected: str, expected: str) -> bool:
    if expected == "pan":
        return detected.startswith("pan")
    if "zoom" in expected:
        return "zoom" in detected
    return detected == expected


def _mark(detected: str, expected: str) -> str:
    return "✓" if _match(detected, expected) else "✗"


def run_video(case: dict, shot_step_sec: float = 1.0) -> None:
    video_path = Path(case["path"])
    video_id = case["video_id"]
    ts = case["ts"]
    expected = case["expected"]

    log(f"\n{'='*76}")
    log(f"[{video_id}]  SQL ts={ts}s  GT={expected}  ({case['sql_tag']})")

    # 1. SQL GT 추출
    stills = _parse_gt_from_sql(video_id)
    gt_label: str | None = None
    if stills:
        for still in stills:
            label = _normalize_motion(still.get("visual_elements", []))
            if label:
                gt_label = label
                break

    # 2. 샷 감지
    shots, fps, total = detect_shots(video_path)
    log(f"  shots={len(shots)}  fps={fps:.1f}  total={total}f ({total/fps:.1f}s)")
    log(shots_summary(shots, fps))

    # 3. GT 타임스탬프가 속한 샷 인덱스
    gt_shot_idx = find_shot_for_ts(shots, ts, fps)

    # 4. 각 샷별 분석
    step = max(1, int(shot_step_sec * fps))
    col_w = 11

    log(f"\n  {'Shot':>5}  {'구간':>18}  {'OSH':>{col_w}}  {'Farneback':>{col_w}}  {'LK':>{col_w}}  GT?")
    log(f"  {'-'*5}  {'-'*18}  {'-'*col_w}  {'-'*col_w}  {'-'*col_w}  ---")

    results_at_gt: dict[str, str] = {}
    for i, (s, e) in enumerate(shots):
        frames = extract_shot_frames(video_path, s, e, step)
        if len(frames) < 2:
            osh = fb = lk = "too_short"
        else:
            osh = osh_motion_for_shot(frames)
            fb  = fb_mod.motion_for_shot(frames)
            lk  = lk_mod.motion_for_shot(frames)

        span = f"{s/fps:.1f}s~{e/fps:.1f}s"
        gt_marker = ""
        if i == gt_shot_idx:
            gt_marker = f"★(ts={ts}s)"
            results_at_gt = {"osh": osh, "fb": fb, "lk": lk}

        log(f"  {i+1:>5}  {span:>18}  {osh:>{col_w}}  {fb:>{col_w}}  {lk:>{col_w}}  {gt_marker}")

    # 5. GT 샷 일치 여부
    if results_at_gt:
        osh_ok = _mark(results_at_gt["osh"], expected)
        fb_ok  = _mark(results_at_gt["fb"], expected)
        lk_ok  = _mark(results_at_gt["lk"], expected)
        log(f"\n  [GT 일치]  OSH={osh_ok}({results_at_gt['osh']})  "
            f"FB={fb_ok}({results_at_gt['fb']})  LK={lk_ok}({results_at_gt['lk']})")
        return results_at_gt, expected
    else:
        log("  [GT 샷 없음 — ts 가 감지된 샷 밖]")
        return {}, expected


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="GT / OSH / FB / LK 샷 단위 비교")
    parser.add_argument("--step-sec", dest="step_sec", type=float, default=1.0)
    parser.add_argument("--threshold", type=float, default=28.0, help="샷 감지 임계값 (기본 28)")
    args = parser.parse_args()

    # threshold를 shot_detect 기본값으로 반영하기 위해 monkeypatch
    import pikk_tagging.optical_flow.shot_detect as sd
    _orig = sd.detect_shots
    def _patched(path, **kw):
        kw.setdefault("threshold", args.threshold)
        return _orig(path, **kw)
    sd.detect_shots = _patched

    osh_correct = fb_correct = lk_correct = 0
    for case in TEST_CASES:
        ret = run_video(case, shot_step_sec=args.step_sec)
        if isinstance(ret, tuple):
            detected, expected = ret
            if detected:
                if _match(detected.get("osh", ""), expected): osh_correct += 1
                if _match(detected.get("fb", ""), expected):  fb_correct  += 1
                if _match(detected.get("lk", ""), expected):  lk_correct  += 1

    n = len(TEST_CASES)
    log(f"\n{'='*76}")
    log(f"[최종 정확도]  OSH={osh_correct}/{n}  Farneback={fb_correct}/{n}  LK={lk_correct}/{n}")

    sd.detect_shots = _orig


if __name__ == "__main__":
    main()
