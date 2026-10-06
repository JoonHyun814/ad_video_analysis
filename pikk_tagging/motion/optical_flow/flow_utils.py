"""공통 유틸리티 — 프레임 추출, 영상 메타, 로그."""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np


def video_meta(video_path: Path) -> dict:
    """FPS, 전체 프레임 수, 해상도 반환."""
    cap = cv2.VideoCapture(str(video_path))
    meta = {
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    }
    cap.release()
    return meta


def extract_window(
    video_path: Path,
    ts: float,
    fps: float,
    window_sec: float = 5.0,
    step_sec: float = 1.0,
) -> list[tuple[int, np.ndarray]]:
    """ts ±window_sec 구간에서 step_sec 간격으로 그레이스케일 프레임 추출.

    step_sec을 크게 잡으면 느린 줌도 누적 displacement가 감지 가능 수준이 된다.
    """
    step = max(1, int(step_sec * fps))
    start_f = max(0, int((ts - window_sec) * fps))
    end_f = int((ts + window_sec) * fps)

    cap = cv2.VideoCapture(str(video_path))
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
    frames: list[tuple[int, np.ndarray]] = []
    idx = start_f
    while idx <= end_f:
        ret, frame = cap.read()
        if not ret:
            break
        if (idx - start_f) % step == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            frames.append((idx, gray))
        idx += 1
    cap.release()
    return frames


def extract_full(
    video_path: Path,
    step: int = 30,
) -> list[tuple[int, np.ndarray]]:
    """영상 전체에서 step 프레임마다 그레이스케일 추출."""
    cap = cv2.VideoCapture(str(video_path))
    frames: list[tuple[int, np.ndarray]] = []
    idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if idx % step == 0:
            frames.append((idx, cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)))
        idx += 1
    cap.release()
    return frames


def log(msg: str) -> None:
    sys.stdout.buffer.write((msg + "\n").encode("utf-8", errors="replace"))
    sys.stdout.buffer.flush()
