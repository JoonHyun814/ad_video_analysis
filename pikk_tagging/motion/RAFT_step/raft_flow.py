"""RAFT 광학 흐름 — step 간격 연속 프레임 쌍 분석.

분류 없이 FlowStats raw 값만 반환한다.
torchvision >= 0.13 필요.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import torch


@dataclass
class StepResult:
    """프레임 쌍 하나의 RAFT 결과 (raw stats)."""
    frame_a: int
    frame_b: int
    time_a: float
    time_b: float
    stats: object           # FlowStats
    flow: np.ndarray | None  # (H, W, 2) float32 | None


def load_model(
    device: str = "cpu",
    model_size: str = "large",
    model_dir: str | None = None,
) -> tuple[torch.nn.Module, object]:
    try:
        from torchvision.models.optical_flow import (
            raft_large, raft_small,
            Raft_Large_Weights, Raft_Small_Weights,
        )
    except ImportError:
        raise SystemExit("pip install torchvision (>= 0.13)")

    if model_dir:
        import pathlib
        pathlib.Path(model_dir).mkdir(parents=True, exist_ok=True)
        torch.hub.set_dir(model_dir)

    if model_size == "small":
        weights = Raft_Small_Weights.DEFAULT
        model = raft_small(weights=weights)
    else:
        weights = Raft_Large_Weights.DEFAULT
        model = raft_large(weights=weights)

    return model.eval().to(device), weights.transforms()


def _bgr_to_tensor(frame_bgr: np.ndarray, device: str) -> torch.Tensor:
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    return torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0).to(device)


def _pad8(img: torch.Tensor) -> tuple[torch.Tensor, tuple[int, int]]:
    import torch.nn.functional as F
    _, _, h, w = img.shape
    ph, pw = (8 - h % 8) % 8, (8 - w % 8) % 8
    if ph or pw:
        img = F.pad(img, [0, pw, 0, ph])
    return img, (h, w)


def compute_flow_pair(model, transforms, t1: torch.Tensor, t2: torch.Tensor) -> np.ndarray:
    t1p, (h, w) = _pad8(t1)
    t2p, _ = _pad8(t2)
    t1t, t2t = transforms(t1p, t2p)
    with torch.no_grad():
        flows = model(t1t, t2t)
    flow = flows[-1][0].cpu().numpy()
    return np.transpose(flow, (1, 2, 0))[:h, :w, :]


def analyze_by_step(
    video_path: Path,
    model,
    transforms,
    device: str = "cpu",
    step: int = 10,
    resize: tuple[int, int] | None = (640, 360),
) -> tuple[list[StepResult], float, int]:
    """step 프레임 간격 전체 영상 RAFT → raw FlowStats 반환.

    Returns:
        (results, fps, total_frames)
    """
    from .motion_classify import flow_to_stats

    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    needed: set[int] = set()
    for fa in range(0, total - step, step):
        needed.add(fa)
        needed.add(fa + step)

    frames: dict[int, np.ndarray] = {}
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if idx in needed:
            if resize:
                frame = cv2.resize(frame, resize)
            frames[idx] = frame
        idx += 1
    cap.release()

    results: list[StepResult] = []
    n_pairs = (total - 1) // step
    for i, fa in enumerate(range(0, total - step, step)):
        fb = fa + step
        if fa not in frames or fb not in frames:
            continue
        try:
            t1 = _bgr_to_tensor(frames[fa], device)
            t2 = _bgr_to_tensor(frames[fb], device)
            flow = compute_flow_pair(model, transforms, t1, t2)
            stats = flow_to_stats(flow)
        except Exception as exc:
            _log(f"  오류 frame {fa}→{fb}: {exc}")
            continue

        results.append(StepResult(
            frame_a=fa, frame_b=fb,
            time_a=round(fa / fps, 3), time_b=round(fb / fps, 3),
            stats=stats, flow=flow,
        ))

        if (i + 1) % 50 == 0 or (i + 1) == n_pairs:
            _log(f"  [{i+1}/{n_pairs}] frame {fa}→{fb}  mag={stats.mean_mag:.1f}px")

    _log(f"  완료: {len(results)}쌍  fps={fps:.1f}  total={total}프레임")
    return results, fps, total


def _log(msg: str) -> None:
    sys.stdout.buffer.write((msg + "\n").encode("utf-8", errors="replace"))
    sys.stdout.buffer.flush()
