"""Rule-based camera angle classifier: stats → label.

Labels: dutch_angle | bird_eye | high_angle | eye_level | low_angle
"""
from __future__ import annotations

import math

LABELS = ("dutch_angle", "bird_eye", "high_angle", "eye_level", "low_angle")

# Dutch angle: |roll_angle_deg| > 이 값 → 기울어진 구도
_DUTCH_ROLL = 15.0

# Bird's eye: 수평선 비율 높고 수직선 거의 없음 (납작한 탑뷰 구도)
_BIRDEYE_H_RATIO = 0.65
_BIRDEYE_V_RATIO = 0.10

# Horizon 위치 임계값 (horizon_y_ratio: 0=상단, 1=하단)
_HIGH_ANGLE_Y = 0.35   # horizon 상단 → 카메라가 아래를 향함
_LOW_ANGLE_Y  = 0.65   # horizon 하단 → 카메라가 위를 향함


def classify_frame(stats: dict) -> str:
    """단일 프레임 stats → angle 레이블."""
    if abs(stats["roll_angle_deg"]) > _DUTCH_ROLL:
        return "dutch_angle"

    hy = stats["horizon_y_ratio"]

    # Bird's eye: 수평선이 지배적이고 수직선 없음 (탑뷰 flat lay)
    if (stats["h_line_ratio"] > _BIRDEYE_H_RATIO
            and stats["v_line_ratio"] < _BIRDEYE_V_RATIO
            and stats["line_count"] > 5):
        return "bird_eye"

    if hy < _HIGH_ANGLE_Y:
        return "high_angle"
    if hy > _LOW_ANGLE_Y:
        return "low_angle"
    return "eye_level"


def classify_frame_simple(stats: dict) -> str:
    """roll_angle_deg 만 사용 (horizon 추정 없음) — 실험 비교용."""
    if abs(stats["roll_angle_deg"]) > _DUTCH_ROLL:
        return "dutch_angle"
    return "eye_level"


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

    simple=True 이면 roll_angle 만 사용하는 classify_frame_simple 사용 (실험용).
    """
    clf    = classify_frame_simple if simple else classify_frame
    labels = [clf(f["stats"]) for f in frames]
    labels = _run_length_filter(labels, step=step, min_frames=min_frames)
    return [{**f, "label": l} for f, l in zip(frames, labels)]
