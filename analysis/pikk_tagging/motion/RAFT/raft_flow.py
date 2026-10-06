"""RAFT 광학 흐름 추론 — torchvision.models.optical_flow 사용.

분석 흐름:
  shot_detect() → 샷 목록 → 샷마다 프레임 쌍 1개 추출 → RAFT 1회 → 태그 1개

컷 경계 프레임 쌍은 완전히 제외되고, 샷당 정확히 하나의 태그가 부여된다.

참조: https://github.com/princeton-vl/raft
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
class ShotResult:
    """샷 하나의 RAFT 분석 결과 (프레임 쌍 1개 기준)."""
    shot_idx: int
    start_frame: int
    end_frame: int
    start_sec: float
    end_sec: float
    duration_sec: float
    frame_a: int             # RAFT에 사용한 첫 번째 프레임 번호
    frame_b: int             # RAFT에 사용한 두 번째 프레임 번호
    motion_type: str
    stats: object            # FlowStats | None
    flow: np.ndarray | None  # (H, W, 2) float32 | None


def load_model(
    device: str = "cpu",
    model_size: str = "large",
    model_dir: str | None = None,
) -> tuple[torch.nn.Module, object]:
    """RAFT 모델과 전처리 transforms 반환.

    model_dir: weights 저장 경로. 지정 시 torch.hub.set_dir() 호출.
    첫 호출 시 torchvision이 pretrained weights를 자동 다운로드한다.
    """
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
    """BGR (H,W,3) uint8 → (1,3,H,W) uint8 tensor.

    float32로 변환하지 않고 uint8을 그대로 넘긴다.
    transforms의 F.convert_image_dtype이 uint8일 때만 /255 정규화를 수행하기 때문이다.
    float32로 넘기면 /255 없이 2x-1이 적용되어 flow가 수백 픽셀 단위로 폭발한다.
    """
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    t = torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0)  # uint8 [0,255]
    return t.to(device)


def _pad8(img: torch.Tensor) -> tuple[torch.Tensor, tuple[int, int]]:
    """H, W를 8의 배수로 패딩. 원본 (H, W) 반환."""
    import torch.nn.functional as F
    _, _, h, w = img.shape
    ph = (8 - h % 8) % 8
    pw = (8 - w % 8) % 8
    if ph or pw:
        img = F.pad(img, [0, pw, 0, ph])
    return img, (h, w)


def compute_flow_pair(
    model: torch.nn.Module,
    transforms,
    t1: torch.Tensor,
    t2: torch.Tensor,
) -> np.ndarray:
    """두 프레임 텐서 → flow (H,W,2) numpy float32."""
    t1p, (h, w) = _pad8(t1)
    t2p, _ = _pad8(t2)
    t1t, t2t = transforms(t1p, t2p)
    with torch.no_grad():
        flows = model(t1t, t2t)
    flow = flows[-1][0].cpu().numpy()  # (2, H_padded, W_padded)
    return np.transpose(flow, (1, 2, 0))[:h, :w, :]  # (H, W, 2)


def _read_frame(cap: cv2.VideoCapture, frame_idx: int,
                resize: tuple[int, int] | None) -> np.ndarray | None:
    """지정 프레임 번호 읽기. 실패 시 None."""
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ret, frame = cap.read()
    if not ret:
        return None
    return cv2.resize(frame, resize) if resize else frame


def analyze_by_shots(
    video_path: Path,
    model: torch.nn.Module,
    transforms,
    device: str = "cpu",
    step: int = 25,
    resize: tuple[int, int] | None = (640, 360),
) -> tuple[list[ShotResult], float]:
    """컷 감지 → 샷 단위 RAFT 분석.

    각 샷에서 (start_frame, start_frame+step) 프레임 쌍 1개만 추출해 RAFT를 1회 실행한다.
    결과는 샷당 태그 1개로 명확하게 출력된다.

    step이 샷 길이보다 길면 (start_frame, end_frame) 쌍을 사용한다.

    Returns:
        (shot_results, fps)
    """
    from .motion_classify import classify_flow
    from ..optical_flow.shot_detect import detect_shots

    shots, fps, _ = detect_shots(video_path)
    _log(f"  [RAFT] 샷 감지: {len(shots)}개  fps={fps:.1f}")

    cap = cv2.VideoCapture(str(video_path))
    shot_results: list[ShotResult] = []

    for i, (s, e) in enumerate(shots):
        fa = s
        fb = min(s + step, e)

        if fa >= fb:
            shot_results.append(_make_result(i, s, e, fps, fa, fb,
                                             "too_short", None, None))
            _log(f"  shot {i+1:>2}/{len(shots)}  {s/fps:.1f}~{e/fps:.1f}s → too_short")
            continue

        bgr_a = _read_frame(cap, fa, resize)
        bgr_b = _read_frame(cap, fb, resize)
        if bgr_a is None or bgr_b is None:
            shot_results.append(_make_result(i, s, e, fps, fa, fb,
                                             "read_error", None, None))
            continue

        try:
            t1 = _bgr_to_tensor(bgr_a, device)
            t2 = _bgr_to_tensor(bgr_b, device)
            flow = compute_flow_pair(model, transforms, t1, t2)
            motion, stats = classify_flow(flow)
        except Exception as exc:
            _log(f"  [RAFT] 오류 shot {i} frame {fa}→{fb}: {exc}")
            shot_results.append(_make_result(i, s, e, fps, fa, fb,
                                             "error", None, None))
            continue

        shot_results.append(_make_result(i, s, e, fps, fa, fb, motion, stats, flow))
        _log(f"  shot {i+1:>2}/{len(shots)}"
             f"  {s/fps:.1f}~{e/fps:.1f}s"
             f"  [{fa}→{fb}]"
             f"  → {motion}"
             f"  mag={stats.mean_mag:.1f}px")

    cap.release()
    return shot_results, fps


def _make_result(
    shot_idx: int, s: int, e: int, fps: float,
    fa: int, fb: int, motion: str, stats, flow,
) -> ShotResult:
    return ShotResult(
        shot_idx=shot_idx,
        start_frame=s, end_frame=e,
        start_sec=round(s / fps, 2), end_sec=round(e / fps, 2),
        duration_sec=round((e - s) / fps, 2),
        frame_a=fa, frame_b=fb,
        motion_type=motion,
        stats=stats,
        flow=flow,
    )


def _log(msg: str) -> None:
    sys.stdout.buffer.write((msg + "\n").encode("utf-8", errors="replace"))
    sys.stdout.buffer.flush()
