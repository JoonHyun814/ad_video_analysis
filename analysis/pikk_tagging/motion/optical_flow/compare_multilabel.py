"""GT 멀티라벨 / Farneback / LK 샷 단위 결과 비교.

python -m pikk_tagging.motion.optical_flow.compare_multilabel
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from collections import defaultdict

from .shot_detect import detect_shots, find_shot_for_ts, extract_shot_frames
from utils.env_loader import get_data_root
from .flow_utils import log
from . import farneback as fb_mod
from . import lucas_kanade as lk_mod
from ..OSH.feature_match import motion_for_shot as osh_motion_for_shot

_SQL_PATH = get_data_root() / "stills_pikk.sql"
_VIDEO_BASE = get_data_root() / "pikk_output" / "motion_test"

# SQL visual_elements → 정규화된 모션 레이블 (다중 키워드)
_GT_MAP: list[tuple[str, list[str]]] = [
    ("zoom_in",  ["줌인", "줌 인", "push-in", "push in", "slow push", "슬로우 줌", "zoom in", "zoom-in"]),
    ("zoom_out", ["줌아웃", "줌 아웃", "zoom out", "zoom-out", "반전 줌아웃", "점진적 줌 아웃"]),
    ("pan",      ["패닝", "팬 샷", "팬기법", "panning", "pan shot"]),
    ("tilt",     ["틸트", "tilt up", "tilt down", "틸트업", "틸트다운"]),
    ("handheld", ["핸드헬드", "handheld", "핸드 헬드"]),
    ("tracking", ["트래킹", "tracking"]),
    ("static",   ["정적", "스태틱", "static", "고정"]),
]

# 테스트 케이스: (video_id, ts, expected_labels)
# ts = SQL의 timestamp_seconds; expected_labels는 런타임에 SQL에서 자동 갱신
# NOTE: B3CrNh1ri5I "틸트 앵글"은 더치앵글(정적 구도)이며 카메라 무빙 아님 → 오탐 예상
#       89k0B9fjkBA "위성 줌인" / KccntjIMKQI "줌인 트랜지션" → CG/디지털 효과 가능성
TEST_CASES = [
    # 기존 4개
    ("81HnwNayElo",  24, ["zoom_in"]),
    ("DtQWxnQAwec",   7, ["zoom_out"]),
    ("7SDum-LuYZg",  45, ["pan"]),
    ("IEd24npXNUI",  22, ["zoom_out"]),
    # zoom_in
    ("89k0B9fjkBA",  33, ["zoom_in"]),     # "위성 줌인 인트로" (CG일 수 있음)
    ("KccntjIMKQI",  52, ["zoom_in"]),     # "줌인 트랜지션" (디지털 효과 가능성)
    # zoom_out
    ("5Qr07Yobj_4",  42, ["zoom_out"]),
    # pan
    ("2qkZ-FGbx-Q",  99, ["pan"]),
    ("3u93XGv8GZY",  10, ["pan"]),
    # tilt
    ("0UFazoY57Ek",  67, ["tilt"]),        # "로우앵글 틸트업" — 명확한 tilt
    ("47LJ80qnQYs",  19, ["tilt"]),        # "더치앵글/틸트 무빙" — 무빙 포함
    ("B3CrNh1ri5I",   2, ["tilt"]),        # "다이내믹 틸트 앵글 (Dutch Angle)" — 정적 구도 가능성
    # handheld
    ("-5lAx7309cE", 108, ["handheld"]),
    ("-DgpW5J9ruE",   9, ["handheld"]),
    ("-J5WTOXBIzo",  45, ["handheld"]),
]


def _normalize_labels(visual_elements: list[str]) -> list[str]:
    """visual_elements → 중복 없는 레이블 리스트."""
    joined = " ".join(visual_elements).lower()
    return [label for label, kws in _GT_MAP if any(kw.lower() in joined for kw in kws)]


def _parse_gt_from_sql(video_id: str) -> list[str]:
    """SQL에서 video_id의 모션 레이블 추출."""
    key = f'"video_id":"{video_id}"'
    with _SQL_PATH.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if key not in line:
                continue
            s, e = line.find("{"), line.rfind("}")
            if s < 0 or e <= s:
                continue
            try:
                obj = json.loads(line[s:e+1])
                labels = _normalize_labels(obj.get("visual_elements", []))
                if labels:
                    return labels
            except Exception:
                pass
    return []


def _match(detected: str, gt_labels: list[str]) -> bool:
    """감지 레이블이 GT 레이블 중 하나라도 일치하면 True."""
    for gt in gt_labels:
        if gt == "pan" and detected.startswith("pan"):
            return True
        if gt == "tilt" and detected == "tilt":
            return True
        if "zoom" in gt and "zoom" in detected:
            if gt == detected:
                return True
        if gt == detected:
            return True
    return False


def _find_video(video_id: str) -> Path | None:
    d = _VIDEO_BASE / video_id
    if not d.exists():
        return None
    # 직접 경로 우선
    for ext in (".mp4", ".webm", ".mkv"):
        p = d / f"{video_id}{ext}"
        if p.exists():
            return p
    # download_one이 하위 디렉토리에 저장하는 경우 재귀 탐색
    for ext in (".mp4", ".webm", ".mkv"):
        hits = list(d.rglob(f"{video_id}{ext}"))
        if hits:
            return hits[0]
    return None


def run_video(
    video_id: str, ts: float, gt_labels: list[str], step_sec: float = 1.0
) -> dict | None:
    """단일 영상 샷 단위 분석 → GT 샷 감지 결과 dict."""
    video_path = _find_video(video_id)
    if video_path is None:
        log(f"  [skip] {video_id} — 파일 없음")
        return None

    # SQL에서 GT 갱신 (수동 기재보다 우선)
    sql_labels = _parse_gt_from_sql(video_id)
    effective_gt = sql_labels if sql_labels else gt_labels

    log(f"\n{'='*72}")
    log(f"[{video_id}]  ts={ts}s  GT={effective_gt}")

    shots, fps, total = detect_shots(video_path)
    step = max(1, int(step_sec * fps))

    gt_shot_idx = find_shot_for_ts(shots, ts, fps)
    if gt_shot_idx is None:
        log(f"  shots={len(shots)}, ts={ts}s가 감지된 샷 범위 밖 — 마지막 샷으로 대체")
        gt_shot_idx = len(shots) - 1

    best_results: dict[str, str] = {}
    for i, (s, e) in enumerate(shots):
        frames = extract_shot_frames(video_path, s, e, step)
        if len(frames) < 2:
            results = {"osh": "too_short", "fb": "too_short", "lk": "too_short"}
        else:
            results = {
                "osh": osh_motion_for_shot(frames),
                "fb":  fb_mod.motion_for_shot(frames),
                "lk":  lk_mod.motion_for_shot(frames),
            }
        if i == gt_shot_idx:
            best_results = results

    fb_ok  = _match(best_results.get("fb", ""), effective_gt)
    lk_ok  = _match(best_results.get("lk", ""), effective_gt)
    osh_ok = _match(best_results.get("osh", ""), effective_gt)

    log(f"  GT샷 shots={len(shots)}  idx={gt_shot_idx+1}/{len(shots)}")
    log(f"  OSH={best_results.get('osh')} {'✓' if osh_ok else '✗'}  "
        f"FB={best_results.get('fb')} {'✓' if fb_ok else '✗'}  "
        f"LK={best_results.get('lk')} {'✓' if lk_ok else '✗'}")

    return {
        "video_id": video_id,
        "gt": effective_gt,
        "osh": best_results.get("osh", ""),
        "fb":  best_results.get("fb", ""),
        "lk":  best_results.get("lk", ""),
        "osh_ok": osh_ok, "fb_ok": fb_ok, "lk_ok": lk_ok,
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="멀티라벨 GT / OSH / FB / LK 샷 단위 비교")
    parser.add_argument("--step-sec", dest="step_sec", type=float, default=1.0)
    args = parser.parse_args()

    all_results: list[dict] = []
    for vid, ts, gt_labels in TEST_CASES:
        r = run_video(vid, ts, gt_labels, step_sec=args.step_sec)
        if r:
            all_results.append(r)

    if not all_results:
        log("\n[결과 없음]")
        return

    # 레이블별 정확도 집계
    by_label: dict[str, dict] = defaultdict(lambda: {"osh": 0, "fb": 0, "lk": 0, "n": 0})
    for r in all_results:
        primary = r["gt"][0] if r["gt"] else "unknown"
        by_label[primary]["n"] += 1
        if r["osh_ok"]: by_label[primary]["osh"] += 1
        if r["fb_ok"]:  by_label[primary]["fb"]  += 1
        if r["lk_ok"]:  by_label[primary]["lk"]  += 1

    n_total = len(all_results)
    osh_total = sum(r["osh_ok"] for r in all_results)
    fb_total  = sum(r["fb_ok"]  for r in all_results)
    lk_total  = sum(r["lk_ok"]  for r in all_results)

    log(f"\n{'='*72}")
    log(f"{'레이블':<12} {'n':>4}  {'OSH':>8}  {'Farneback':>10}  {'LK':>8}")
    log(f"{'-'*12} {'-'*4}  {'-'*8}  {'-'*10}  {'-'*8}")
    for label in ["zoom_in", "zoom_out", "pan", "tilt", "handheld"]:
        d = by_label.get(label)
        if not d or d["n"] == 0:
            continue
        n = d["n"]
        log(f"{label:<12} {n:>4}  {d['osh']:>3}/{n:<4}  {d['fb']:>4}/{n:<5}  {d['lk']:>3}/{n}")
    log(f"{'합계':<12} {n_total:>4}  {osh_total:>3}/{n_total:<4}  {fb_total:>4}/{n_total:<5}  {lk_total:>3}/{n_total}")

    # 감지 안 된 케이스 목록
    log(f"\n--- 오분류 상세 ---")
    for r in all_results:
        if not r["fb_ok"] or not r["lk_ok"]:
            log(f"  {r['video_id']:<16} GT={r['gt']}  FB={r['fb']}  LK={r['lk']}")


if __name__ == "__main__":
    main()
