"""RAFT flow (H,W,2) → FlowStats → 모션 분류.

optical_flow.motion_type 의 FlowStats / aggregate 를 재사용하되,
RAFT + step=25(1초 간격) 전용 임계값을 별도로 정의한다.

Farneback(연속 프레임)과 달리 RAFT는 1초 간격 프레임 쌍을 비교하므로
누적 변위가 크다. 같은 임계값을 쓰면 정적 샷도 pan/rotate로 오분류된다.
"""
from __future__ import annotations

import numpy as np

from ..optical_flow.motion_type import FlowStats

# ── RAFT 전용 임계값 (motion_type.py 기본값보다 높음) ────────────────────────
# 평균 흐름 크기 기준: 이 값 미만 → static (step=25 1초 간격 기준 ~5px)
_MIN_MAG_MOTION: float = 5.0

# 640px 프레임 절반 너비
_HALF_W: float = 320.0

# zoom: divergence 임계값 (motion_type 0.01 → RAFT 0.015)
_ZOOM_THRESH: float = 0.015
# pan: 픽셀/HALF_W 비율 임계값 (motion_type 0.005≈1.6px → RAFT 0.012≈3.8px)
_PAN_FRAC_THRESH: float = 0.012
# rotate: curl 임계값 (motion_type 0.015 → RAFT 0.020)
_ROT_THRESH: float = 0.020


def flow_to_stats(flow_hw2: np.ndarray) -> FlowStats:
    """dense flow (H,W,2) → FlowStats.

    farneback.py 의 dense_flow_stats 와 동일한 공식 — 서브샘플 없이 전체 픽셀 사용.
    """
    u = flow_hw2[:, :, 0]
    v = flow_hw2[:, :, 1]

    pan_x = float(np.mean(u))
    pan_y = float(np.mean(v))

    zoom_score = float(np.mean(np.gradient(u, axis=1) + np.gradient(v, axis=0)))
    rotation_score = float(np.mean(np.gradient(v, axis=1) - np.gradient(u, axis=0)))

    mag = np.sqrt(u**2 + v**2)
    return FlowStats(
        zoom_score=zoom_score,
        pan_x=pan_x,
        pan_y=pan_y,
        rotation_score=rotation_score,
        flow_var=float(np.var(mag)),
        mean_mag=float(np.mean(mag)),
        n_valid=u.size,
    )


def classify_flow(flow_hw2: np.ndarray) -> tuple[str, FlowStats]:
    """flow → (motion_type, FlowStats) — RAFT 전용 임계값 사용.

    mean_mag < _MIN_MAG_MOTION 이면 static 으로 단락 처리.
    motion_type.classify() 대신 이 함수로 직접 분류해 over-sensitivity를 방지한다.
    """
    stats = flow_to_stats(flow_hw2)
    if stats.mean_mag < _MIN_MAG_MOTION:
        return "static", stats

    zoom = abs(stats.zoom_score)
    pan_frac = max(abs(stats.pan_x), abs(stats.pan_y)) / _HALF_W
    rot = abs(stats.rotation_score)

    if zoom > _ZOOM_THRESH and zoom > pan_frac * 1.5 and zoom > rot * 2.0:
        return ("zoom_in" if stats.zoom_score > 0 else "zoom_out"), stats
    if rot > _ROT_THRESH and rot > pan_frac:
        return "rotate", stats
    if pan_frac > _PAN_FRAC_THRESH:
        if abs(stats.pan_x) >= abs(stats.pan_y):
            return ("pan_right" if stats.pan_x > 0 else "pan_left"), stats
        return ("pan_down" if stats.pan_y > 0 else "pan_up"), stats
    return "static", stats
