"""Frame-level camera angle features via Hough line transform (OpenCV).

사용:
    from pikk_tagging.angle.analyzer import analyze_video
    result = analyze_video("path/to/video.mp4", step=30)
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

import cv2
import numpy as np

_HOUGH_THRESHOLD = 80   # Hough 누적 임계값 (클수록 길고 강한 선만 검출)
_MAX_LINES       = 200  # 최대 검출 선 수


def analyze_frame(frame: np.ndarray) -> dict[str, float]:
    """BGR frame → angle stats dict."""
    gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w    = gray.shape
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges   = cv2.Canny(blurred, 50, 150)

    lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=_HOUGH_THRESHOLD)

    if lines is None or len(lines) == 0:
        return {
            "roll_angle_deg":   0.0,
            "horizon_y_ratio":  0.5,
            "h_line_ratio":     0.0,
            "v_line_ratio":     0.0,
            "line_count":       0,
        }

    lines = lines[:_MAX_LINES, 0, :]          # (N, 2) — rho, theta
    thetas_deg = np.degrees(lines[:, 1])      # 0°=수직선, 90°=수평선
    n = len(thetas_deg)

    # 수평선 (theta 60°~120°), 수직선 (0°~20° 또는 160°~180°)
    near_h = (thetas_deg > 60) & (thetas_deg < 120)
    near_v = (thetas_deg < 20) | (thetas_deg > 160)
    h_line_ratio = float(near_h.sum() / n)
    v_line_ratio = float(near_v.sum() / n)

    # Roll angle: 수평선들의 theta 편차 (90° 기준)
    if near_h.sum() > 0:
        roll_angle_deg = float(np.median(thetas_deg[near_h]) - 90.0)
    else:
        roll_angle_deg = 0.0

    # Horizon y 추정: 수평선(theta ≈ 90°)의 y 절편
    h_idxs = np.where(near_h)[0]
    if len(h_idxs) > 0:
        rhos   = lines[h_idxs, 0]
        thetas = lines[h_idxs, 1]
        x_mid  = w / 2.0
        sin_t  = np.sin(thetas)
        cos_t  = np.cos(thetas)
        # rho = x*cos(t) + y*sin(t) → y = (rho - x*cos(t)) / sin(t)
        y_vals = (rhos - x_mid * cos_t) / (sin_t + 1e-6)
        valid  = (y_vals > 0) & (y_vals < h)
        if valid.sum() > 0:
            horizon_y_ratio = float(np.clip(np.median(y_vals[valid]) / h, 0.0, 1.0))
        else:
            horizon_y_ratio = 0.5
    else:
        horizon_y_ratio = 0.5

    return {
        "roll_angle_deg":  round(roll_angle_deg, 2),
        "horizon_y_ratio": round(horizon_y_ratio, 4),
        "h_line_ratio":    round(h_line_ratio, 4),
        "v_line_ratio":    round(v_line_ratio, 4),
        "line_count":      int(n),
    }


def _frame_iter(
    cap: cv2.VideoCapture,
    step: int,
) -> Iterator[tuple[int, float, np.ndarray]]:
    fps   = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    idx   = 0
    while idx < total:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            break
        yield idx, round(idx / fps, 3), frame
        idx += step


def analyze_video(video_path: str | Path, step: int = 30) -> dict:
    """step 프레임 간격으로 angle stats 를 수집해 결과 dict 반환."""
    path = Path(video_path)
    cap  = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise FileNotFoundError(f"영상을 열 수 없음: {path}")

    fps          = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frames: list[dict] = []
    try:
        for idx, t, frame in _frame_iter(cap, step):
            stats = analyze_frame(frame)
            frames.append({"frame": idx, "time": t, "stats": stats})
    finally:
        cap.release()

    return {
        "video":        str(path),
        "fps":          round(fps, 3),
        "step":         step,
        "total_frames": total_frames,
        "frames":       frames,
    }
