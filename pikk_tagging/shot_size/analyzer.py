"""Frame-level shot size features via face detection + edge analysis (OpenCV).

사용:
    from pikk_tagging.shot_size.analyzer import analyze_video
    result = analyze_video("path/to/video.mp4", step=30)
    # result["frames"][i] = {frame, time, stats}
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

import cv2
import numpy as np

_CASCADE = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

_CENTER_Y = (0.20, 0.80)
_CENTER_X = (0.20, 0.80)


def _center_slices(h: int, w: int) -> tuple[slice, slice]:
    y0, y1 = int(h * _CENTER_Y[0]), int(h * _CENTER_Y[1])
    x0, x1 = int(w * _CENTER_X[0]), int(w * _CENTER_X[1])
    return slice(y0, y1), slice(x0, x1)


def analyze_frame(frame: np.ndarray) -> dict[str, float]:
    """BGR frame → shot size stats dict."""
    gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w    = gray.shape
    total   = h * w

    faces = _CASCADE.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30),
        flags=cv2.CASCADE_SCALE_IMAGE,
    )

    if len(faces) > 0:
        areas = [fw * fh for (_, _, fw, fh) in faces]
        fx, fy, fw, fh = faces[int(np.argmax(areas))]
        face_h_ratio   = fh / h
        face_area_ratio = (fw * fh) / total
        face_center_y  = (fy + fh / 2) / h
    else:
        face_h_ratio   = 0.0
        face_area_ratio = 0.0
        face_center_y  = 0.5

    # Edge density (피사체 크기 대리 지표 — 얼굴 없는 컷용)
    edges   = cv2.Canny(gray, 50, 150)
    total_e = float(edges.sum()) / 255
    sy, sx  = _center_slices(h, w)
    center_e = float(edges[sy, sx].sum()) / 255
    c_area   = (sy.stop - sy.start) * (sx.stop - sx.start)

    edge_density       = total_e / total
    center_edge_density = center_e / c_area if c_area > 0 else 0.0
    center_edge_ratio   = center_edge_density / (edge_density + 1e-6)

    return {
        "face_detected":     1.0 if len(faces) > 0 else 0.0,
        "face_h_ratio":      round(face_h_ratio, 4),
        "face_area_ratio":   round(face_area_ratio, 4),
        "face_center_y":     round(face_center_y, 4),
        "edge_density":      round(edge_density, 6),
        "center_edge_ratio": round(float(center_edge_ratio), 4),
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
    """step 프레임 간격으로 shot size stats 를 수집해 결과 dict 반환."""
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
