"""Frame-level lighting stats via pixel analysis (OpenCV).

사용:
    from pikk_tagging.lighting.analyzer import analyze_video
    result = analyze_video("path/to/video.mp4", step=30)
    # result["frames"][i] = {frame, time, stats}
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

import cv2
import numpy as np

_DARK_THRESH      = 60    # 이 값 이하 픽셀 → shadow
_BRIGHT_THRESH    = 200   # 이 값 이상 픽셀 → highlight

# center 영역 (역광 감지용 배경/전경 분리)
_CENTER_Y = (0.25, 0.75)
_CENTER_X = (0.20, 0.80)


def _gray(frame: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def _center_slices(h: int, w: int) -> tuple[slice, slice]:
    y0, y1 = int(h * _CENTER_Y[0]), int(h * _CENTER_Y[1])
    x0, x1 = int(w * _CENTER_X[0]), int(w * _CENTER_X[1])
    return slice(y0, y1), slice(x0, x1)


def analyze_frame(frame: np.ndarray) -> dict[str, float]:
    """BGR frame → lighting stats dict."""
    gray  = _gray(frame)
    h, w  = gray.shape
    total = h * w

    mean_b = float(gray.mean())
    std_b  = float(gray.std())
    shadow_ratio    = float((gray < _DARK_THRESH).sum()   / total)
    highlight_ratio = float((gray > _BRIGHT_THRESH).sum() / total)

    sy, sx = _center_slices(h, w)
    center_brightness = float(gray[sy, sx].mean())

    bg_mask = np.ones((h, w), dtype=bool)
    bg_mask[sy, sx] = False
    bg_brightness  = float(gray[bg_mask].mean())
    bg_center_ratio = bg_brightness / (center_brightness + 1e-6)

    return {
        "mean_brightness":   round(mean_b, 2),
        "brightness_std":    round(std_b, 2),
        "shadow_ratio":      round(shadow_ratio, 4),
        "highlight_ratio":   round(highlight_ratio, 4),
        "center_brightness": round(center_brightness, 2),
        "bg_brightness":     round(bg_brightness, 2),
        "bg_center_ratio":   round(bg_center_ratio, 4),
    }


def _frame_iter(
    cap: cv2.VideoCapture,
    step: int,
) -> Iterator[tuple[int, float, np.ndarray]]:
    """step 프레임마다 (frame_idx, time_sec, frame) 반환."""
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
    """step 프레임 간격으로 조명 stats 를 수집해 결과 dict 반환."""
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
