"""훅 구간 RAFT 카메라 모션 분석.

pikk_tagging.motion.RAFT_step 의 raft_flow / motion_classify / smooth 를 재사용.
모델은 배치 처리 효율을 위해 모듈 싱글턴으로 유지한다.
"""
from __future__ import annotations

import gc
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import torch

from hook_pipeline.config import ensure_legacy_on_path

MOTION_FILE = "camera_motion.json"

_raft_model = None
_raft_transforms = None
_raft_device: str = "cpu"
_raft_model_size: str = "large"


@dataclass
class _RaftCtx:
    model: object
    transforms: object
    device: str


def _get_raft(device: str, model_size: str, model_dir: str | None) -> _RaftCtx:
    global _raft_model, _raft_transforms, _raft_device, _raft_model_size
    if _raft_model is None:
        ensure_legacy_on_path()
        from pikk_tagging.motion.RAFT_step.raft_flow import load_model
        print(f"  [RAFT] 모델 로드 ({model_size}, {device})")
        _raft_model, _raft_transforms = load_model(device, model_size, model_dir)
        _raft_device = device
        _raft_model_size = model_size
    return _RaftCtx(_raft_model, _raft_transforms, _raft_device)


def release_raft() -> None:
    """배치 종료 시 RAFT 모델을 내려 GPU 메모리를 비운다."""
    global _raft_model, _raft_transforms
    _raft_model = None
    _raft_transforms = None
    gc.collect()
    try:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def analyze_hook_camera_motion(
    video_path: Path,
    hook_frame_count: int,
    fps: float,
    device: str = "cuda",
    model_size: str = "large",
    step: int = 3,
    model_dir: str | None = None,
    resize: tuple[int, int] = (640, 360),
) -> dict:
    """훅 구간(첫 hook_frame_count 프레임)의 RAFT 카메라 모션을 분석하고 요약 dict 를 반환한다.

    Returns:
        step, fps, hook_frame_count, n_pairs, dominant_label,
        label_counts, mean_mag, pairs (smooth_and_classify 결과)
    """
    ensure_legacy_on_path()
    from pikk_tagging.motion.RAFT_step.motion_classify import flow_to_stats
    from pikk_tagging.motion.RAFT_step.raft_flow import compute_flow_pair
    from pikk_tagging.motion.RAFT_step.smooth import smooth_and_classify

    ctx = _get_raft(device, model_size, model_dir)
    k = hook_frame_count

    # 필요한 프레임 인덱스 수집 (step 간격 쌍)
    needed: set[int] = set()
    for fa in range(0, k - step, step):
        needed.add(fa)
        needed.add(fa + step)

    # 프레임 읽기 (훅 구간만)
    cap = cv2.VideoCapture(str(video_path))
    frames: dict[int, np.ndarray] = {}
    for idx in range(k):
        ret, frame = cap.read()
        if not ret:
            break
        if idx in needed:
            frames[idx] = cv2.resize(frame, resize) if resize else frame
    cap.release()

    # RAFT flow 계산
    raw_pairs: list[dict] = []
    for fa in range(0, k - step, step):
        fb = fa + step
        if fa not in frames or fb not in frames:
            continue
        try:
            t1 = _bgr_to_tensor(frames[fa], ctx.device)
            t2 = _bgr_to_tensor(frames[fb], ctx.device)
            flow = compute_flow_pair(ctx.model, ctx.transforms, t1, t2)
            st = flow_to_stats(flow)
        except Exception as exc:
            print(f"  [RAFT] frame {fa}→{fb} 오류: {exc}")
            continue
        raw_pairs.append({
            "frame_a": fa, "frame_b": fb,
            "time_a": round(fa / fps, 3), "time_b": round(fb / fps, 3),
            "stats": {
                "zoom_score":     round(st.zoom_score, 6),
                "pan_x":          round(st.pan_x, 4),
                "pan_y":          round(st.pan_y, 4),
                "rotation_score": round(st.rotation_score, 6),
                "flow_var":       round(st.flow_var, 4),
                "mean_mag":       round(st.mean_mag, 4),
                "n_valid":        st.n_valid,
            },
        })

    if not raw_pairs:
        return {
            "step": step, "fps": round(fps, 3),
            "hook_frame_count": k, "n_pairs": 0,
            "dominant_label": "unknown",
            "label_counts": {}, "mean_mag": 0.0, "pairs": [],
        }

    # 후처리: 스파이크 제거 + 누적 fallback 분류 + temporal filter
    # acc_window=9 는 step=10 기준 설계치; step=3 이면 9스텝=27프레임(~0.9s) 누적
    smoothed = smooth_and_classify(raw_pairs, step=step, min_frames=6, acc_window=9)

    labels = [r["label"] for r in smoothed]
    label_counts: dict[str, int] = {}
    for lb in labels:
        label_counts[lb] = label_counts.get(lb, 0) + 1
    dominant = max(label_counts, key=label_counts.__getitem__)
    mean_mag = round(
        sum(r["stats"]["mean_mag"] for r in smoothed) / len(smoothed), 2
    )

    return {
        "step": step,
        "fps": round(fps, 3),
        "hook_frame_count": k,
        "n_pairs": len(smoothed),
        "dominant_label": dominant,
        "label_counts": label_counts,
        "mean_mag": mean_mag,
        "pairs": [
            {
                "frame_a":  r["frame_a"],
                "frame_b":  r["frame_b"],
                "time_a":   r["time_a"],
                "time_b":   r["time_b"],
                "label":    r["label"],
                "is_spike": r["is_spike"],
                "stats":    r["stats"],
            }
            for r in smoothed
        ],
    }


def format_for_prompt(cm: dict) -> str:
    """camera_motion dict → LLM 프롬프트 삽입용 텍스트."""
    if not cm or cm.get("n_pairs", 0) == 0:
        return ""
    labels = [p["label"] for p in cm.get("pairs", [])]
    seq = " → ".join(labels) if labels else "—"
    counts_str = ", ".join(f"{lb}:{n}" for lb, n in sorted(cm["label_counts"].items(), key=lambda x: -x[1]))
    return (
        f"[Camera Motion — RAFT optical flow, step={cm['step']} frames, hook period]\n"
        f"Dominant motion: {cm['dominant_label']}\n"
        f"Sequence: {seq}\n"
        f"Label distribution: {counts_str}\n"
        f"Mean flow magnitude: {cm['mean_mag']:.1f} px/step\n"
    )


def _bgr_to_tensor(frame_bgr: np.ndarray, device: str) -> torch.Tensor:
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    return torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0).to(device)
