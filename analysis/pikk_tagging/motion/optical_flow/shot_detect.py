"""프레임 차이(frame difference) 기반 샷 경계 감지.

모든 프레임을 축소 크기로 읽어 인접 프레임 평균 절대 오차(MAE)를 계산하고,
임계값을 초과하면 샷 경계로 판단한다.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .flow_utils import log


def detect_shots(
    video_path: Path,
    threshold: float = 28.0,
    min_shot_sec: float = 1.5,
    resize_w: int = 160,
) -> tuple[list[tuple[int, int]], float, int]:
    """프레임 차이 기반 샷 경계 감지.

    Returns:
        (shots, fps, total_frames)
        shots: list of (start_frame, end_frame) — 두 경계 포함.
    """
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    min_frames = int(min_shot_sec * fps)

    prev_gray: np.ndarray | None = None
    frame_idx = 0
    cut_frames: list[int] = [0]

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        h, w = frame.shape[:2]
        scale = resize_w / w
        small = cv2.resize(frame, (resize_w, max(1, int(h * scale))))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32)

        if prev_gray is not None:
            mae = float(np.mean(np.abs(gray - prev_gray)))
            if mae > threshold:
                last_cut = cut_frames[-1]
                if frame_idx - last_cut >= min_frames:
                    cut_frames.append(frame_idx)

        prev_gray = gray
        frame_idx += 1

    cap.release()

    shots: list[tuple[int, int]] = []
    for i, start in enumerate(cut_frames):
        end = cut_frames[i + 1] - 1 if i + 1 < len(cut_frames) else total - 1
        shots.append((start, end))

    return shots, fps, total


def shots_summary(shots: list[tuple[int, int]], fps: float) -> str:
    lines = []
    for i, (s, e) in enumerate(shots):
        dur = (e - s) / fps
        lines.append(f"  Shot {i+1:>2}: frames {s:>5}~{e:>5}  ({s/fps:.1f}s ~ {e/fps:.1f}s  dur={dur:.1f}s)")
    return "\n".join(lines)


def find_shot_for_ts(shots: list[tuple[int, int]], ts: float, fps: float) -> int | None:
    """ts(초)가 속한 샷 인덱스(0-based) 반환. 없으면 None."""
    target_frame = int(ts * fps)
    for i, (s, e) in enumerate(shots):
        if s <= target_frame <= e:
            return i
    return None


def extract_shot_frames(
    video_path: Path,
    start_frame: int,
    end_frame: int,
    step: int,
) -> list[tuple[int, np.ndarray]]:
    """샷 구간에서 step 간격으로 그레이스케일 프레임 추출."""
    cap = cv2.VideoCapture(str(video_path))
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    frames: list[tuple[int, np.ndarray]] = []
    idx = start_frame
    while idx <= end_frame:
        ret, frame = cap.read()
        if not ret:
            break
        if (idx - start_frame) % step == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            frames.append((idx, gray))
        idx += 1
    cap.release()
    return frames
