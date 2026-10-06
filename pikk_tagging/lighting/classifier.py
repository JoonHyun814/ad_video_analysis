"""Rule-based lighting classifier: stats → label.

Labels: high_key | low_key | backlight | normal
"""
from __future__ import annotations

import math

LABELS = ("high_key", "low_key", "backlight", "normal")

# ── backlight: 배경 밝고 중앙 어두움 ──────────────────────────────────────────
_BL_RATIO   = 1.45   # bg_center_ratio 임계값
_BL_BG_MIN  = 115.0  # 배경 밝기 최솟값
_BL_CTR_MAX = 105.0  # 중앙 밝기 최댓값

# ── high key: 전체적으로 밝고 그림자 적음 ────────────────────────────────────
_HK_MEAN    = 155.0
_HK_SHADOW  = 0.12

# ── low key: 전체적으로 어둡고 그림자 많음 ────────────────────────────────────
_LK_MEAN    = 82.0
_LK_SHADOW  = 0.38


def classify_frame(stats: dict) -> str:
    """단일 프레임 stats dict → 레이블."""
    if (stats["bg_center_ratio"] > _BL_RATIO
            and stats["bg_brightness"] > _BL_BG_MIN
            and stats["center_brightness"] < _BL_CTR_MAX):
        return "backlight"

    if (stats["mean_brightness"] > _HK_MEAN
            and stats["shadow_ratio"] < _HK_SHADOW):
        return "high_key"

    if (stats["mean_brightness"] < _LK_MEAN
            and stats["shadow_ratio"] > _LK_SHADOW):
        return "low_key"

    return "normal"


def classify_frame_simple(stats: dict) -> str:
    """mean_brightness 만 사용 (공간 분석 없음) — 실험 비교용."""
    if stats["mean_brightness"] > _HK_MEAN:
        return "high_key"
    if stats["mean_brightness"] < _LK_MEAN:
        return "low_key"
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
    """frame 결과 리스트에 label 추가 + temporal run-length filter 적용.

    simple=True 이면 공간 분석 없는 classify_frame_simple 사용 (실험용).
    """
    clf    = classify_frame_simple if simple else classify_frame
    labels = [clf(f["stats"]) for f in frames]
    labels = _run_length_filter(labels, step=step, min_frames=min_frames)
    return [{**f, "label": l} for f, l in zip(frames, labels)]
