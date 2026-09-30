"""Frame-level focus/DOF features via Laplacian variance (OpenCV).

사용:
    from pikk_tagging.focus.analyzer import analyze_video
    result = analyze_video("path/to/video.mp4", step=30)
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

import cv2
import numpy as np

_CENTER_Y = (0.20, 0.80)
_CENTER_X = (0.20, 0.80)


def _center_slices(h: int, w: int) -> tuple[slice, slice]:
    y0, y1 = int(h * _CENTER_Y[0]), int(h * _CENTER_Y[1])
    x0, x1 = int(w * _CENTER_X[0]), int(w * _CENTER_X[1])
    return slice(y0, y1), slice(x0, x1)


def _lap_var(gray_patch: np.ndarray) -> float:
    if gray_patch.shape[0] < 3 or gray_patch.shape[1] < 3:
        return 0.0
    return float(cv2.Laplacian(gray_patch, cv2.CV_64F).var())


def analyze_frame(frame: np.ndarray) -> dict[str, float]:
    """BGR frame → focus stats dict."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    sy, sx = _center_slices(h, w)

    global_sharpness = _lap_var(gray)
    center_sharpness = _lap_var(gray[sy, sx])

    # 배경 영역: 4개 코너 스트립의 평균 Laplacian variance
    bg_patches = [
        gray[:sy.start, :],
        gray[sy.stop:, :],
        gray[sy.start:sy.stop, :sx.start],
        gray[sy.start:sy.stop, sx.stop:],
    ]
    bg_vars = [_lap_var(p) for p in bg_patches if p.size > 0]
    bg_sharpness = float(np.mean(bg_vars)) if bg_vars else center_sharpness

    center_bg_ratio = center_sharpness / (bg_sharpness + 1e-6)

    return {
        "global_sharpness":  round(min(global_sharpness, 9999.0), 2),
        "center_sharpness":  round(min(center_sharpness, 9999.0), 2),
        "bg_sharpness":      round(min(bg_sharpness, 9999.0), 2),
        "center_bg_ratio":   round(min(float(center_bg_ratio), 20.0), 4),
        "sharpness_delta":   0.0,  # analyze_video 에서 시간축 delta 채움
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
    """step 프레임 간격으로 focus stats 를 수집해 결과 dict 반환."""
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

    # 시간축 sharpness 변화량 계산 (rack focus 감지용)
    for i in range(1, len(frames)):
        prev = frames[i - 1]["stats"]["global_sharpness"]
        curr = frames[i]["stats"]["global_sharpness"]
        frames[i]["stats"]["sharpness_delta"] = round(abs(curr - prev), 2)

    return {
        "video":        str(path),
        "fps":          round(fps, 3),
        "step":         step,
        "total_frames": total_frames,
        "frames":       frames,
    }
