"""Farneback Dense Optical Flow 기반 카메라 모션 분석.

step_sec=1.0 (1초 간격) 기본값: 느린 줌도 누적 displacement가 감지 가능 범위.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .flow_utils import extract_window, extract_full, video_meta, log
from .motion_type import FlowStats, MotionResult, dense_flow_stats, classify, aggregate

# Farneback 파라미터 — levels=4로 최대 16px 변위까지 처리
_FB = dict(pyr_scale=0.5, levels=4, winsize=25, iterations=3,
           poly_n=7, poly_sigma=1.5, flags=0)


def compute_flow(prev: np.ndarray, curr: np.ndarray) -> np.ndarray:
    """두 그레이스케일 프레임 → Farneback dense flow (H,W,2)."""
    return cv2.calcOpticalFlowFarneback(prev, curr, None, **_FB)


def analyze_pair(
    frame_a: int, frame_b: int,
    gray_a: np.ndarray, gray_b: np.ndarray,
) -> MotionResult:
    """프레임 쌍 하나의 Farneback 분석."""
    flow = compute_flow(gray_a, gray_b)
    stats = dense_flow_stats(flow)
    return MotionResult(
        frame_a=frame_a, frame_b=frame_b,
        method="farneback",
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
    """영상 전체를 step 프레임 간격으로 Farneback 분석."""
    frames = extract_full(video_path, step)
    log(f"  [Farneback] 추출 프레임: {len(frames)} (step={step})")
    return analyze_shot(frames)


def motion_for_shot(frames: list[tuple[int, np.ndarray]]) -> str:
    """샷 내 연속 프레임 쌍을 분석해 지배 모션 유형 반환 (Farneback)."""
    results = analyze_shot(frames)
    return aggregate(results)


def print_results(results: list[MotionResult], video_name: str = "") -> None:
    from collections import Counter
    counts = Counter(r.motion_type for r in results)
    valid = [r for r in results if r.motion_type != "cut"]
    avg_zoom = sum(r.stats.zoom_score for r in valid) / len(valid) if valid else 0
    avg_pan = sum(abs(r.stats.pan_x) for r in valid) / len(valid) if valid else 0
    avg_mag = sum(r.stats.mean_mag for r in valid) / len(valid) if valid else 0
    dominant = aggregate(results)

    log(f"\n[Farneback] {video_name}")
    log(f"  지배 모션  : {dominant}")
    log(f"  분포       : {dict(counts)}")
    log(f"  avg zoom   : {avg_zoom:.5f}  avg pan: {avg_pan:.2f}px  avg mag: {avg_mag:.2f}px")
    log(f"  zoom trend : {[round(r.stats.zoom_score,5) for r in results[:10]]}")
