"""DHF1K 영상 프레임 추출 및 saliency/fixation 오버레이."""

import io
import os
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

_BSDTAR = "C:/Windows/System32/tar.exe"
_ALPHA = 0.55  # 오버레이 투명도


@lru_cache(maxsize=20)
def _get_avi_tmpfile(rar_path: str, vid: str) -> str:
    """video.rar에서 AVI를 추출해 임시 파일 경로를 반환한다 (캐시됨)."""
    member = f"video/{int(vid):03d}.AVI"
    result = subprocess.run(
        [_BSDTAR, "-xf", rar_path, "-O", member],
        capture_output=True,
    )
    if result.returncode != 0 or not result.stdout:
        raise FileNotFoundError(member)
    tmp = tempfile.NamedTemporaryFile(suffix=".avi", delete=False)
    tmp.write(result.stdout)
    tmp.close()
    return tmp.name


def read_frame(video_rar: str, vid: str, frame_idx: int) -> tuple[Image.Image, int]:
    """AVI에서 frame_idx 번 프레임을 읽어 PIL 이미지로 반환한다.

    Returns:
        (frame_image, total_frames)
    """
    tmp = _get_avi_tmpfile(video_rar, vid)
    cap = cv2.VideoCapture(tmp)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ret, bgr = cap.read()
    cap.release()
    if not ret:
        raise ValueError(f"frame {frame_idx} read failed")
    return Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)), total


def _apply_colormap(gray: np.ndarray) -> np.ndarray:
    """그레이스케일 맵을 JET 컬러맵 RGB로 변환한다."""
    normed = (gray.astype(np.float32) / 255.0 * 255).astype(np.uint8)
    color = cv2.applyColorMap(normed, cv2.COLORMAP_JET)
    return cv2.cvtColor(color, cv2.COLOR_BGR2RGB)


def overlay_sal(frame: Image.Image, sal_png: bytes) -> Image.Image:
    """saliency map을 JET 컬러맵으로 프레임 위에 블렌딩한다."""
    sal = np.array(Image.open(io.BytesIO(sal_png)).convert("L").resize(
        frame.size, Image.BILINEAR))
    colored = _apply_colormap(sal)
    blend = (np.array(frame) * (1 - _ALPHA) + colored * _ALPHA).astype(np.uint8)
    return Image.fromarray(blend)


def overlay_fix(frame: Image.Image, fix_png: bytes) -> Image.Image:
    """fixation map을 빨간 점으로 프레임 위에 오버레이한다."""
    fix = np.array(Image.open(io.BytesIO(fix_png)).convert("L").resize(
        frame.size, Image.BILINEAR))
    result = np.array(frame).copy()
    mask = fix > 30
    result[mask] = (result[mask] * 0.3 + np.array([255, 50, 50]) * 0.7).astype(np.uint8)
    return Image.fromarray(result)


def cleanup_tmp(vid: str) -> None:
    """임시 AVI 파일을 삭제한다."""
    try:
        key = None
        for k in _get_avi_tmpfile.cache_info().__dict__:
            pass
        path = _get_avi_tmpfile.cache_info()
        if path:
            os.unlink(path)
    except Exception:
        pass
