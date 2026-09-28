"""Optical flow (H,W,2) → RGB 컬러 이미지 변환.

Middlebury 컬러 휠 방식 — 방향이 색상, 크기가 채도로 인코딩된다.
원본 RAFT 시각화 코드(princeton-vl/raft) 기반.
"""
from __future__ import annotations

import numpy as np


def make_colorwheel() -> np.ndarray:
    """55×3 Middlebury 컬러 휠 (uint8 RGB) 생성."""
    RY, YG, GC, CB, BM, MR = 15, 6, 4, 11, 13, 6
    ncols = RY + YG + GC + CB + BM + MR
    cw = np.zeros((ncols, 3), dtype=np.uint8)
    col = 0

    cw[col:col+RY, 0] = 255
    cw[col:col+RY, 1] = (255 * np.arange(RY) / RY).astype(np.uint8)
    col += RY

    cw[col:col+YG, 0] = (255 - 255 * np.arange(YG) / YG).astype(np.uint8)
    cw[col:col+YG, 1] = 255
    col += YG

    cw[col:col+GC, 1] = 255
    cw[col:col+GC, 2] = (255 * np.arange(GC) / GC).astype(np.uint8)
    col += GC

    cw[col:col+CB, 1] = (255 - 255 * np.arange(CB) / CB).astype(np.uint8)
    cw[col:col+CB, 2] = 255
    col += CB

    cw[col:col+BM, 2] = 255
    cw[col:col+BM, 0] = (255 * np.arange(BM) / BM).astype(np.uint8)
    col += BM

    cw[col:col+MR, 2] = (255 - 255 * np.arange(MR) / MR).astype(np.uint8)
    cw[col:col+MR, 0] = 255
    return cw


_CW = make_colorwheel()
_NCOLS = len(_CW)


def _compute_color(u: np.ndarray, v: np.ndarray) -> np.ndarray:
    h, w = u.shape
    img = np.zeros((h, w, 3), dtype=np.uint8)
    nan_mask = np.isnan(u) | np.isnan(v)
    u = np.where(nan_mask, 0.0, u)
    v = np.where(nan_mask, 0.0, v)

    rad = np.sqrt(u**2 + v**2)
    angle = np.arctan2(-v, -u) / np.pi          # [-1, 1]
    fk = (angle + 1) / 2 * (_NCOLS - 1)         # [0, ncols-1]
    k0 = np.floor(fk).astype(int) % _NCOLS
    k1 = (k0 + 1) % _NCOLS
    f = (fk - np.floor(fk))[:, :, np.newaxis]   # (H, W, 1)

    c0 = _CW[k0].astype(np.float32) / 255.0     # (H, W, 3)
    c1 = _CW[k1].astype(np.float32) / 255.0
    col = (1.0 - f) * c0 + f * c1               # bilinear interp
    col = 1.0 - rad[:, :, np.newaxis] * (1.0 - col)  # desaturate low-mag
    col[nan_mask] = 0.0
    img = np.clip(col * 255.0, 0, 255).astype(np.uint8)
    return img


def flow_to_image(flow_hw2: np.ndarray, clip_flow: float | None = None) -> np.ndarray:
    """flow (H,W,2) → RGB uint8 이미지 (H,W,3).

    방향 = 색상, 크기 = 채도(밝음). clip_flow: 최대 변위 픽셀 클리핑.
    """
    assert flow_hw2.ndim == 3 and flow_hw2.shape[2] == 2
    u = flow_hw2[:, :, 0].copy()
    v = flow_hw2[:, :, 1].copy()
    if clip_flow is not None:
        u = np.clip(u, -clip_flow, clip_flow)
        v = np.clip(v, -clip_flow, clip_flow)

    rad_max = np.sqrt(u**2 + v**2).max()
    eps = np.finfo(np.float32).eps
    u /= (rad_max + eps)
    v /= (rad_max + eps)
    return _compute_color(u, v)
