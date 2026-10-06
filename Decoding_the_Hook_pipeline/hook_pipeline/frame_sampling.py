"""논문 3.2 Two Frame Sampling Strategies — 훅 구간(K 프레임)에서 m 개 프레임 인덱스를 고른다."""
from collections.abc import Iterator
from pathlib import Path

import cv2
import numpy as np
from skimage.metrics import structural_similarity

_SSIM_HEIGHT = 360  # SSIM 계산용 축소 높이 (속도 목적, 선택된 프레임은 원본 해상도로 저장)


def hook_frame_count(video_path: Path, hook_sec: float) -> tuple[int, float]:
    """훅 구간 프레임 수 K 와 fps 를 반환한다. 예: fps=30, 3초 → K=90."""
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    k = int(round(fps * hook_sec))
    return (min(k, total) if total > 0 else k), fps


def random_sampling(k: int, m: int, seed: int) -> list[int]:
    """K 프레임 중 m 개를 균등·독립적으로 무작위 선택한다."""
    rng = np.random.default_rng(seed)
    return sorted(int(i) for i in rng.choice(k, size=min(m, k), replace=False))


def keyframe_selection(video_path: Path, k: int, alpha: float, min_interval: int) -> tuple[list[int], list[float]]:
    """D_i = 1 - SSIM(I_i, I_{i+1}), τ = α·max(D), {I_i | D_i > τ} 에 최소 간격 Δt 를 적용한다."""
    diffs = _ssim_differences(video_path, k)
    if not diffs or max(diffs) <= 0:
        return [0], diffs  # 정지 화면: 변화가 없으면 첫 프레임만 사용
    tau = alpha * max(diffs)
    selected: list[int] = []
    for i, d in enumerate(diffs):
        if d > tau and (not selected or i - selected[-1] >= min_interval):
            selected.append(i)
    return selected, diffs


def _ssim_differences(video_path: Path, k: int) -> list[float]:
    diffs: list[float] = []
    prev = None
    for _, frame in _iter_frames(video_path, k):
        gray = _to_small_gray(frame)
        if prev is not None:
            diffs.append(1.0 - float(structural_similarity(prev, gray, data_range=255)))
        prev = gray
    return diffs


def _to_small_gray(frame: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    if h > _SSIM_HEIGHT:
        gray = cv2.resize(gray, (int(w * _SSIM_HEIGHT / h), _SSIM_HEIGHT), interpolation=cv2.INTER_AREA)
    return gray


def _iter_frames(video_path: Path, k: int) -> Iterator[tuple[int, np.ndarray]]:
    cap = cv2.VideoCapture(str(video_path))
    try:
        for i in range(k):
            ok, frame = cap.read()
            if not ok:
                break
            yield i, frame
    finally:
        cap.release()


def save_frames(video_path: Path, indices: list[int], fps: float, out_dir: Path) -> list[dict]:
    """선택된 인덱스의 원본 프레임을 JPG 로 저장하고 [{index, time_sec, path}] 를 반환한다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    wanted = set(indices)
    saved: list[dict] = []
    for i, frame in _iter_frames(video_path, max(indices) + 1):
        if i not in wanted:
            continue
        t = i / fps
        path = out_dir / f"frame_{i:03d}_{t:.2f}s.jpg"
        path.write_bytes(cv2.imencode(".jpg", frame)[1].tobytes())  # 비ASCII 경로 대응
        saved.append({"index": i, "time_sec": round(t, 3), "path": str(path.resolve())})
    return saved
