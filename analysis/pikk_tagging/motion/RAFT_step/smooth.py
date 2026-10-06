"""RAFT_step 결과 후처리 — 스파이크 제거 + 누적 fallback 분류.

사용:
    from pikk_tagging.motion.RAFT_step.smooth import smooth_and_classify
    rows = smooth_and_classify(pairs, step=5, min_frames=10, acc_window=5)
    # rows[i] = {frame_a, frame_b, time_a, time_b, label, stats, is_spike}

분류 전략:
  1. 단일 스텝 stats로 먼저 분류
  2. 결과가 static/motion(신호 약함)이면 acc_window 구간 합산 stats로 재시도
     → zoom_in/zoom_out만 승격 허용 (pan/rotation은 배경 노이즈 누적 오탐 방지)
  3. 빠른 모션(이미 zoom/pan/rotate)은 단일 스텝 결과를 그대로 사용
"""
from __future__ import annotations

import math
from typing import Any

# ── 분류 임계값 (step=10, 0.4s 간격 기준) ───────────────────────────────────
_MIN_MAG = 3.0          # px 미만 → static
_ZOOM_THRESH = 0.05     # zoom_score 절댓값
_PAN_THRESH = 5.0       # pan_x / pan_y 절댓값 (px)
_ROT_THRESH = 0.015     # rotation_score 절댓값

# ── 스파이크 감지 파라미터 ────────────────────────────────────────────────────
_SPIKE_WINDOW = 5       # 중앙값 계산에 사용할 양쪽 이웃 수
_SPIKE_FACTOR = 3.0     # 중앙값 대비 배율 이상이면 스파이크
_SPIKE_MIN_MAG = 15.0   # 이 값 이상일 때만 스파이크로 판단

_FIELDS = ("zoom_score", "pan_x", "pan_y", "rotation_score", "flow_var", "mean_mag")


def _median(vals: list[float]) -> float:
    s = sorted(vals)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def detect_spikes(pairs: list[dict], window: int = _SPIKE_WINDOW) -> set[int]:
    """mean_mag 기준 스파이크 인덱스 집합 반환."""
    n = len(pairs)
    mags = [p["stats"]["mean_mag"] for p in pairs]
    spikes: set[int] = set()
    for i in range(n):
        lo, hi = max(0, i - window), min(n, i + window + 1)
        neighbors = [mags[j] for j in range(lo, hi) if j != i]
        if not neighbors:
            continue
        med = _median(neighbors)
        if mags[i] > _SPIKE_MIN_MAG and med > 0 and mags[i] / med >= _SPIKE_FACTOR:
            spikes.add(i)
    return spikes


def _interp_stats(pairs: list[dict], spikes: set[int]) -> list[dict]:
    """스파이크 위치의 stats를 이웃 비스파이크 값으로 보간."""
    n = len(pairs)
    result = [dict(p) for p in pairs]

    for i in spikes:
        # 왼쪽/오른쪽 비스파이크 이웃 탐색
        left = next((j for j in range(i - 1, -1, -1) if j not in spikes), None)
        right = next((j for j in range(i + 1, n) if j not in spikes), None)

        if left is None and right is None:
            continue
        elif left is None:
            src = pairs[right]["stats"]
        elif right is None:
            src = pairs[left]["stats"]
        else:
            # 거리 가중 선형 보간
            dl = i - left
            dr = right - i
            total = dl + dr
            ls, rs = pairs[left]["stats"], pairs[right]["stats"]
            src = {f: ls[f] * dr / total + rs[f] * dl / total for f in _FIELDS}

        result[i] = {**result[i], "stats": {**src}, "is_spike": True}

    return result


def classify_stats(stats: dict) -> str:
    """stats dict → 레이블 문자열.

    우선순위: zoom > pan > rotation
    zoom_score가 threshold 이상이면 pan/rotation 동시 초과 여부와 무관하게 zoom으로 분류.
    rotation은 zoom/pan 신호가 없을 때만 분류.
    """
    mag = stats["mean_mag"]
    if mag < _MIN_MAG:
        return "static"
    zoom = stats["zoom_score"]
    pan_x = abs(stats["pan_x"])
    pan_y = abs(stats["pan_y"])
    rot = abs(stats["rotation_score"])

    zoom_dom = abs(zoom) > _ZOOM_THRESH
    pan_dom = pan_x > _PAN_THRESH or pan_y > _PAN_THRESH
    rot_dom = rot > _ROT_THRESH

    # zoom이 threshold 이상이면 pan/rotation 혼재해도 zoom 우선
    if zoom_dom:
        return "zoom_in" if zoom > 0 else "zoom_out"

    # zoom 없이 pan만 있을 때
    if pan_dom:
        if pan_x >= pan_y:
            return "pan_right" if stats["pan_x"] > 0 else "pan_left"
        return "tilt_down" if stats["pan_y"] > 0 else "tilt_up"

    # zoom/pan 없이 rotation만 있을 때
    if rot_dom:
        return "rotate_cw" if stats["rotation_score"] > 0 else "rotate_ccw"

    return "motion"


def _rolling_sum_stats(pairs: list[dict], window: int) -> list[dict[str, float]]:
    """분류 fallback용: window 스텝 구간 stats 합산.

    zoom_score, pan_x/y, rotation_score는 합산하면 단일 pair에서 step*window 간격으로
    RAFT를 돌린 것과 근사한 값이 된다 (flow 값이 step에 선형 비례하므로).
    느린 카메라 모션처럼 단일 스텝에서 threshold를 못 넘는 신호를 감지하기 위해 사용.
    """
    n = len(pairs)
    half = window // 2
    result: list[dict[str, float]] = []
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        ws = [pairs[j]["stats"] for j in range(lo, hi)]
        result.append({f: sum(s[f] for s in ws) for f in _FIELDS})
    return result


def temporal_filter(labels: list[str], step: int, min_frames: int = 30) -> list[str]:
    """min_frames 미만 지속 레이블을 이웃으로 교체 (run-length 기반)."""
    min_steps = math.ceil(min_frames / step)
    result = list(labels)
    n = len(result)

    changed = True
    while changed:
        changed = False
        i = 0
        while i < n:
            # 현재 레이블의 연속 구간 길이 측정
            j = i
            while j < n and result[j] == result[i]:
                j += 1
            run_len = j - i
            if run_len < min_steps:
                left_label = result[i - 1] if i > 0 else None
                right_label = result[j] if j < n else None
                # 더 긴 이웃 레이블로 대체 (없으면 어느 쪽이든)
                replace = left_label or right_label
                if replace and replace != result[i]:
                    for k in range(i, j):
                        result[k] = replace
                    changed = True
            i = j

    return result


def smooth_and_classify(
    pairs: list[dict],
    step: int = 5,
    min_frames: int = 10,
    acc_window: int = 9,
) -> list[dict[str, Any]]:
    """스파이크 제거 → 누적 fallback 분류 → 최소 지속 필터 적용 결과 반환.

    Args:
        acc_window: 단일 스텝 분류가 static/motion일 때 재시도할 누적 윈도우 크기.
                    step=5 기준 acc_window=9 → 45프레임(1.8s) 누적 — 느린 줌 감지용.
    """
    spikes = detect_spikes(pairs)
    smoothed = _interp_stats(pairs, spikes)
    acc_stats = _rolling_sum_stats(smoothed, window=acc_window)

    labels: list[str] = []
    for p, acc in zip(smoothed, acc_stats):
        label = classify_stats(p["stats"])
        if label in ("static", "motion"):
            # 누적 fallback은 zoom 전용:
            # pan/rotation은 방향이 무작위인 배경 노이즈가 누적 합산에서
            # 임계값을 넘는 오탐이 발생하므로 zoom_in/zoom_out만 승격 허용.
            acc_label = classify_stats(acc)
            if acc_label in ("zoom_in", "zoom_out"):
                label = acc_label
        labels.append(label)

    labels = temporal_filter(labels, step=step, min_frames=min_frames)

    rows = []
    for p, label in zip(smoothed, labels):
        rows.append({
            "frame_a":  p["frame_a"],
            "frame_b":  p["frame_b"],
            "time_a":   p["time_a"],
            "time_b":   p["time_b"],
            "label":    label,
            "is_spike": p.get("is_spike", False),
            "stats":    p["stats"],
            "flow_viz": p.get("flow_viz"),
        })
    return rows
