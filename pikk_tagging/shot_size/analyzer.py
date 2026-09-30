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

_MODEL_PATH = Path(__file__).parent / "models" / "face_detection_yunet_2023mar.onnx"
_DETECTOR: cv2.FaceDetectorYN | None = None
_DETECTOR_SIZE: tuple[int, int] = (0, 0)

_CENTER_Y = (0.20, 0.80)
_CENTER_X = (0.20, 0.80)


def _get_detector(w: int, h: int) -> cv2.FaceDetectorYN:
    """입력 해상도에 맞춰 FaceDetectorYN 인스턴스를 (재)생성."""
    global _DETECTOR, _DETECTOR_SIZE
    size = (w, h)
    if _DETECTOR is None or _DETECTOR_SIZE != size:
        _DETECTOR = cv2.FaceDetectorYN_create(
            str(_MODEL_PATH), "", size, score_threshold=0.5, nms_threshold=0.3
        )
        _DETECTOR_SIZE = size
    return _DETECTOR


def _center_slices(h: int, w: int) -> tuple[slice, slice]:
    y0, y1 = int(h * _CENTER_Y[0]), int(h * _CENTER_Y[1])
    x0, x1 = int(w * _CENTER_X[0]), int(w * _CENTER_X[1])
    return slice(y0, y1), slice(x0, x1)


def analyze_frame(frame: np.ndarray) -> dict[str, float]:
    """BGR frame → shot size stats dict."""
    h, w = frame.shape[:2]
    total = h * w

    detector = _get_detector(w, h)
    _, detections = detector.detect(frame)

    if detections is not None and len(detections) > 0:
        # YuNet: [x, y, w, h, ...] — largest face by area
        areas = detections[:, 2] * detections[:, 3]
        best  = detections[int(np.argmax(areas))]
        fx, fy, fw, fh = float(best[0]), float(best[1]), float(best[2]), float(best[3])
        face_h_ratio    = fh / h
        face_area_ratio = (fw * fh) / total
        face_center_y   = (fy + fh / 2) / h
    else:
        face_h_ratio    = 0.0
        face_area_ratio = 0.0
        face_center_y   = 0.5

    # Edge density (피사체 크기 대리 지표 — 얼굴 없는 컷용)
    gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges   = cv2.Canny(gray, 50, 150)
    total_e = float(edges.sum()) / 255
    sy, sx  = _center_slices(h, w)
    center_e = float(edges[sy, sx].sum()) / 255
    c_area   = (sy.stop - sy.start) * (sx.stop - sx.start)

    edge_density        = total_e / total
    center_edge_density = center_e / c_area if c_area > 0 else 0.0
    center_edge_ratio   = center_edge_density / (edge_density + 1e-6)

    face_detected = detections is not None and len(detections) > 0
    return {
        "face_detected":     1.0 if face_detected else 0.0,
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
