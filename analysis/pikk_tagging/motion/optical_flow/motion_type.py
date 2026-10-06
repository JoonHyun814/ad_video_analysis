"""Optical Flow 벡터 필드 → 카메라 모션 유형 분류.

divergence(발산) → zoom, mean flow → pan, curl(회전) → rotate.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class FlowStats:
    """프레임 쌍 하나에서 추출한 flow 요약 통계."""
    zoom_score: float    # 양수 = zoom_in, 음수 = zoom_out (divergence 기반)
    pan_x: float         # +오른쪽 / -왼쪽 (픽셀/프레임)
    pan_y: float         # +아래 / -위 (픽셀/프레임)
    rotation_score: float  # 비영 = 회전 (curl 기반)
    flow_var: float      # 흐름 크기 분산 → 핸드헬드/노이즈 지표
    mean_mag: float      # 평균 흐름 크기
    n_valid: int         # 유효 픽셀(또는 트래킹 포인트) 수


@dataclass
class MotionResult:
    frame_a: int
    frame_b: int
    method: str        # "farneback" | "lk"
    motion_type: str   # zoom_in / zoom_out / pan / rotate / static / cut
    stats: FlowStats


# zoom_score는 분수(scale 변화율), pan은 픽셀 → 비교 전 pan을 분수로 정규화
_HALF_W = 320  # 640px 프레임 기준 절반 너비


def classify(stats: FlowStats) -> str:
    """FlowStats → 모션 유형 문자열.

    pan을 프레임 절반 너비로 나눠 zoom_score(분수)와 같은 단위로 비교한다.
    """
    if stats.n_valid < 10:
        return "cut"

    zoom = abs(stats.zoom_score)
    pan_frac = max(abs(stats.pan_x), abs(stats.pan_y)) / _HALF_W
    rot = abs(stats.rotation_score)

    # 지배 성분 결정 (zoom > rotate > pan > static)
    if zoom > 0.01 and zoom > pan_frac * 1.5 and zoom > rot * 2.0:
        return "zoom_in" if stats.zoom_score > 0 else "zoom_out"
    if rot > 0.015 and rot > pan_frac:
        return "rotate"
    if pan_frac > 0.005:  # 640px 프레임 기준 ~1.6px 이상 이동
        pan_x, pan_y = stats.pan_x, stats.pan_y
        if abs(pan_x) >= abs(pan_y):
            return "pan_right" if pan_x > 0 else "pan_left"
        return "pan_down" if pan_y > 0 else "pan_up"
    return "static"


def aggregate(results: list[MotionResult]) -> str:
    """여러 프레임 쌍 결과 → 샷 전체 지배 모션.

    zoom_score와 pan을 같은 단위로 누적 비교.
    pan_y 우세 → tilt, flow_var/mean_mag 비율 고 → handheld.
    """
    if not results:
        return "unknown"
    valid = [r for r in results if r.motion_type != "cut"]
    if not valid:
        return "cut"

    n = len(valid)
    avg_zoom = sum(r.stats.zoom_score for r in valid) / n
    avg_pan_x = sum(r.stats.pan_x for r in valid) / n
    avg_pan_y = sum(r.stats.pan_y for r in valid) / n
    abs_pan_x = abs(avg_pan_x) / _HALF_W
    abs_pan_y = abs(avg_pan_y) / _HALF_W
    avg_pan_frac = max(abs_pan_x, abs_pan_y)
    avg_rot = abs(sum(r.stats.rotation_score for r in valid) / n)
    avg_var = sum(r.stats.flow_var for r in valid) / n
    avg_mag = sum(r.stats.mean_mag for r in valid) / n
    irregularity = avg_var / (avg_mag + 0.1)  # 방향 일관성 없을수록 높음

    if abs(avg_zoom) > 0.008 and abs(avg_zoom) > avg_pan_frac * 1.5:
        return "zoom_in" if avg_zoom > 0 else "zoom_out"
    if avg_rot > 0.012 and avg_rot > avg_pan_frac:
        return "rotate"
    if avg_pan_frac > 0.004:
        # 수직 이동이 수평의 1.5배 이상이면 tilt
        if abs_pan_y > abs_pan_x * 1.5:
            return "tilt"
        return "pan"
    # 뚜렷한 방향 없이 흔들림 — 핸드헬드 판정
    if irregularity > 3.0 and avg_mag > 0.5:
        return "handheld"
    return "static"


def dense_flow_stats(flow: np.ndarray, subsample: int = 4) -> FlowStats:
    """Farneback dense flow array (H,W,2) → FlowStats.

    subsample: 계산 속도를 위해 픽셀 간격.
    """
    u = flow[::subsample, ::subsample, 0]
    v = flow[::subsample, ::subsample, 1]
    h, w = u.shape

    # Pan: 평균 흐름
    pan_x = float(np.mean(u))
    pan_y = float(np.mean(v))

    # Zoom: divergence (∂u/∂x + ∂v/∂y), 픽셀 단위로 정규화
    du_dx = np.gradient(u, axis=1)
    dv_dy = np.gradient(v, axis=0)
    divergence = du_dx + dv_dy
    zoom_score = float(np.mean(divergence))

    # Rotation: curl (∂v/∂x - ∂u/∂y)
    dv_dx = np.gradient(v, axis=1)
    du_dy = np.gradient(u, axis=0)
    curl = dv_dx - du_dy
    rotation_score = float(np.mean(curl))

    mag = np.sqrt(u ** 2 + v ** 2)
    return FlowStats(
        zoom_score=zoom_score,
        pan_x=pan_x, pan_y=pan_y,
        rotation_score=rotation_score,
        flow_var=float(np.var(mag)),
        mean_mag=float(np.mean(mag)),
        n_valid=h * w,
    )


def sparse_flow_stats(
    p0: np.ndarray, p1: np.ndarray, frame_shape: tuple[int, int]
) -> FlowStats:
    """Lucas-Kanade sparse flow 포인트 쌍 → FlowStats.

    p0, p1: shape (N,1,2) float32.
    4-DOF 회귀(tx, ty, Δscale, θ)로 pan과 zoom을 독립 추정.
    """
    h, w = frame_shape
    cx, cy = w / 2.0, h / 2.0

    pts0 = p0.reshape(-1, 2).astype(np.float64)
    pts1 = p1.reshape(-1, 2).astype(np.float64)
    dp = pts1 - pts0

    rx = pts0[:, 0] - cx
    ry = pts0[:, 1] - cy
    n = len(pts0)
    ones = np.ones(n)
    zeros = np.zeros(n)

    # A @ [tx, ty, ds, theta] = [u; v]
    A = np.vstack([
        np.column_stack([ones, zeros, rx, -ry]),
        np.column_stack([zeros, ones, ry, rx]),
    ])
    b = np.concatenate([dp[:, 0], dp[:, 1]])
    params, *_ = np.linalg.lstsq(A, b, rcond=None)
    tx, ty, ds, theta = params.tolist()

    mag = np.sqrt(dp[:, 0] ** 2 + dp[:, 1] ** 2)
    return FlowStats(
        zoom_score=float(ds),          # 순수 스케일 변화 (양수=zoom_in)
        pan_x=float(tx),
        pan_y=float(ty),
        rotation_score=float(theta),
        flow_var=float(np.var(mag)),
        mean_mag=float(np.mean(mag)),
        n_valid=n,
    )
