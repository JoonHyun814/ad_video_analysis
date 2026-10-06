"""Rule-based focus/DOF classifier: stats → label.

Labels: out_of_focus | shallow_dof | rack_focus | deep_focus | normal
"""
from __future__ import annotations

import math

LABELS = ("out_of_focus", "shallow_dof", "rack_focus", "deep_focus", "normal")

# Laplacian variance 기반 임계값
_OOF_SHARPNESS  = 40.0    # 전체 선명도 이하 → out_of_focus (전체 흐림)
_RACK_DELTA     = 700.0   # sharpness_delta 이상 → rack_focus (선명도 급변)
_SHALLOW_RATIO  = 2.5     # center_bg_ratio 이상 → shallow_dof (중앙 선명, 배경 흐림)
_DEEP_MIN_SHARP = 250.0   # deep_focus 인정 최소 선명도
_DEEP_MAX_RATIO = 1.40    # center_bg_ratio 이하 → deep_focus (전체 균일)
_DEEP_MIN_RATIO = 0.70


def classify_frame(stats: dict) -> str:
    """단일 프레임 stats → focus 레이블."""
    if stats["global_sharpness"] < _OOF_SHARPNESS:
        return "out_of_focus"

    if stats["sharpness_delta"] > _RACK_DELTA:
        return "rack_focus"

    if stats["center_bg_ratio"] > _SHALLOW_RATIO:
        return "shallow_dof"

    if (stats["global_sharpness"] > _DEEP_MIN_SHARP
            and _DEEP_MIN_RATIO <= stats["center_bg_ratio"] <= _DEEP_MAX_RATIO):
        return "deep_focus"

    return "normal"


def classify_frame_simple(stats: dict) -> str:
    """global_sharpness 만 사용 (중앙/배경 비교 없음) — 실험 비교용."""
    if stats["global_sharpness"] < _OOF_SHARPNESS:
        return "out_of_focus"
    return "normal"


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

    simple=True 이면 global_sharpness 만 사용하는 classify_frame_simple (실험용).
    """
    clf    = classify_frame_simple if simple else classify_frame
    labels = [clf(f["stats"]) for f in frames]
    labels = _run_length_filter(labels, step=step, min_frames=min_frames)
    return [{**f, "label": l} for f, l in zip(frames, labels)]
