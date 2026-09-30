"""Rule-based shot size classifier: stats → label.

Labels: extreme_close_up | close_up | medium_close_up | medium_shot | long_shot | wide_shot
"""
from __future__ import annotations

import math

LABELS = (
    "extreme_close_up", "close_up", "medium_close_up",
    "medium_shot", "long_shot", "wide_shot",
)

# 얼굴 감지 시: face_h_ratio (얼굴 높이 / 프레임 높이) 임계값
_ECU_H = 0.60
_CU_H  = 0.38
_MCU_H = 0.22
_MS_H  = 0.12
_LS_H  = 0.04

# 얼굴 없을 때: center_edge_ratio 임계값 (제품·사물 클로즈업 감지)
_NOFACE_CU_EDGE = 1.80
_NOFACE_MS_EDGE = 1.35


def classify_frame(stats: dict) -> str:
    """단일 프레임 stats → 레이블 (얼굴 + edge fallback)."""
    if stats["face_detected"] > 0.5:
        h = stats["face_h_ratio"]
        if h > _ECU_H: return "extreme_close_up"
        if h > _CU_H:  return "close_up"
        if h > _MCU_H: return "medium_close_up"
        if h > _MS_H:  return "medium_shot"
        if h > _LS_H:  return "long_shot"
        return "wide_shot"
    # 얼굴 없음 → edge density 기반
    cer = stats["center_edge_ratio"]
    if cer > _NOFACE_CU_EDGE: return "close_up"
    if cer > _NOFACE_MS_EDGE: return "medium_shot"
    return "wide_shot"


def classify_frame_simple(stats: dict) -> str:
    """얼굴 감지만 사용, edge fallback 없음 — 실험 비교용."""
    if stats["face_detected"] > 0.5:
        h = stats["face_h_ratio"]
        if h > _ECU_H: return "extreme_close_up"
        if h > _CU_H:  return "close_up"
        if h > _MCU_H: return "medium_close_up"
        if h > _MS_H:  return "medium_shot"
        if h > _LS_H:  return "long_shot"
        return "wide_shot"
    return "wide_shot"


def _run_length_filter(
    labels: list[str],
    step: int,
    min_frames: int,
) -> list[str]:
    min_steps = max(1, math.ceil(min_frames / step))
    result    = list(labels)
    n         = len(result)
    changed   = True
    while changed:
        changed = False
        i = 0
        while i < n:
            j = i
            while j < n and result[j] == result[i]:
                j += 1
            if j - i < min_steps:
                left  = result[i - 1] if i > 0 else None
                right = result[j]     if j < n else None
                rep   = left or right
                if rep and rep != result[i]:
                    for k in range(i, j):
                        result[k] = rep
                    changed = True
            i = j
    return result


def temporal_smooth(
    frames: list[dict],
    step: int = 30,
    min_frames: int = 30,
    simple: bool = False,
) -> list[dict]:
    """frame 리스트에 label 추가 + temporal run-length filter.

    simple=True 이면 edge fallback 없는 classify_frame_simple 사용 (실험용).
    """
    clf    = classify_frame_simple if simple else classify_frame
    labels = [clf(f["stats"]) for f in frames]
    labels = _run_length_filter(labels, step=step, min_frames=min_frames)
    return [{**f, "label": l} for f, l in zip(frames, labels)]
