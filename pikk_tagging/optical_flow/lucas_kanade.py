"""Lucas-Kanade Sparse Optical Flow 기반 카메라 모션 분석.

GFTT 코너 검출 → PyrLK 추적 → 이동 벡터 분해 (radial/tangential/translational).
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .flow_utils import extract_window, extract_full, video_meta, log
from .motion_type import FlowStats, MotionResult, sparse_flow_stats, classify, aggregate

# GFTT 파라미터
_GFTT = dict(maxCorners=300, qualityLevel=0.01, minDistance=10, blockSize=7)

# PyrLK 파라미터 — levels=4로 최대 16px 변위 처리
_LK = dict(
    winSize=(25, 25),
    maxLevel=4,
    criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.03),
)


def _good_features(gray: np.ndarray) -> np.ndarray | None:
    pts = cv2.goodFeaturesToTrack(gray, **_GFTT)
    return pts  # (N,1,2) float32 or None


def track(
    prev: np.ndarray, curr: np.ndarray, p0: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """p0 → curr 프레임으로 PyrLK 추적. 성공한 포인트만 반환."""
    p1, status, _ = cv2.calcOpticalFlowPyrLK(prev, curr, p0, None, **_LK)
    mask = (status.flatten() == 1)
    return p0[mask], p1[mask]


def analyze_pair(
    frame_a: int, frame_b: int,
    gray_a: np.ndarray, gray_b: np.ndarray,
) -> MotionResult:
    """프레임 쌍 하나의 LK 분석."""
    p0 = _good_features(gray_a)
    if p0 is None or len(p0) < 10:
        empty = FlowStats(0, 0, 0, 0, 0, 0, 0)
        return MotionResult(frame_a, frame_b, "lk", "cut", empty)

    p0_ok, p1_ok = track(gray_a, gray_b, p0)
    if len(p0_ok) < 10:
        empty = FlowStats(0, 0, 0, 0, 0, 0, len(p0_ok))
        return MotionResult(frame_a, frame_b, "lk", "cut", empty)

    stats = sparse_flow_stats(p0_ok, p1_ok, gray_a.shape)
    return MotionResult(
        frame_a=frame_a, frame_b=frame_b,
        method="lk",
        motion_type=classify(stats),
        stats=stats,
    )


def analyze_shot(
    frames: list[tuple[int, np.ndarray]],
) -> list[MotionResult]:
    """프레임 목록 → 연속 쌍별 MotionResult 리스트."""
    results: list[MotionResult] = []
    for i in range(len(frames) - 1):
        fa, ga = frames[i]
        fb, gb = frames[i + 1]
        results.append(analyze_pair(fa, fb, ga, gb))
    return results


def analyze_window(
    video_path: Path,
    ts: float,
    window_sec: float = 5.0,
    step_sec: float = 1.0,
) -> tuple[str, list[MotionResult]]:
    """ts ±window_sec 구간을 분석 → (지배 모션, 쌍별 결과)."""
    meta = video_meta(video_path)
    frames = extract_window(video_path, ts, meta["fps"], window_sec, step_sec)
    results = analyze_shot(frames)
    dominant = aggregate(results)
    return dominant, results


def analyze_full_video(
    video_path: Path,
    step: int = 30,
) -> list[MotionResult]:
    """영상 전체를 step 프레임 간격으로 LK 분석."""
    frames = extract_full(video_path, step)
    log(f"  [LK] 추출 프레임: {len(frames)} (step={step})")
    return analyze_shot(frames)


def motion_for_shot(frames: list[tuple[int, np.ndarray]]) -> str:
    """샷 내 연속 프레임 쌍을 분석해 지배 모션 유형 반환 (Lucas-Kanade)."""
    results = analyze_shot(frames)
    return aggregate(results)


def print_results(results: list[MotionResult], video_name: str = "") -> None:
    from collections import Counter
    counts = Counter(r.motion_type for r in results)
    valid = [r for r in results if r.motion_type != "cut"]
    avg_zoom = sum(r.stats.zoom_score for r in valid) / len(valid) if valid else 0
    avg_pan = sum(abs(r.stats.pan_x) for r in valid) / len(valid) if valid else 0
    avg_pts = sum(r.stats.n_valid for r in valid) / len(valid) if valid else 0
    dominant = aggregate(results)

    log(f"\n[LK] {video_name}")
    log(f"  지배 모션  : {dominant}")
    log(f"  분포       : {dict(counts)}")
    log(f"  avg zoom   : {avg_zoom:.5f}  avg pan: {avg_pan:.2f}px  avg pts: {avg_pts:.0f}")
    log(f"  zoom trend : {[round(r.stats.zoom_score,5) for r in results[:10]]}")
