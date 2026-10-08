"""Hollywood-2 gaze 데이터 파싱 + 프레임 오버레이."""

import io
import zipfile
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

# subject별 색상 (RGB)
_COLORS = [
    (255, 80,  80),   # s0 red
    (80,  200, 80),   # s1 green
    (80,  140, 255),  # s2 blue
    (255, 200, 50),   # s3 yellow
    (200, 80,  255),  # s4 purple
]
_RADIUS = 6
_ALPHA = 180  # 투명도 0-255


def _parse_coord(text: str) -> tuple[tuple[int, int], list[tuple[int, float, float, float]]]:
    """coord 파일 파싱 → (w, h), [(timestamp_us, x, y, conf), ...]"""
    w, h = 576, 304
    samples: list[tuple[int, float, float, float]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("gaze"):
            parts = line.split()
            w, h = int(parts[1]), int(parts[2])
            continue
        if line.startswith("geometry"):
            continue
        parts = line.split()
        if len(parts) >= 4:
            try:
                samples.append((int(parts[0]), float(parts[1]),
                                 float(parts[2]), float(parts[3])))
            except ValueError:
                pass
    return (w, h), samples


@lru_cache(maxsize=32)
def _load_subject_gaze(zip_path: str, clip_id: str) -> tuple[str, tuple[int, int], list]:
    """zip에서 clip_id에 해당하는 coord 파일을 읽어 파싱한다.

    Returns:
        (subject_id, (w, h), [(timestamp_us, x, y, conf), ...])
    """
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        target = next(
            (n for n in names if clip_id in n and n.endswith(".coord")
             and not n.startswith("__MACOSX")),
            None,
        )
        if target is None:
            return Path(zip_path).stem, (576, 304), []
        sid = target.split("_")[0]
        text = zf.read(target).decode("utf-8", errors="replace")
    resolution, samples = _parse_coord(text)
    return sid, resolution, samples


def load_gaze_for_frame(
    gaze_dir: Path,
    clip_id: str,
    frame_idx: int,
    fps: float,
) -> list[tuple[str, list[tuple[float, float]]]]:
    """프레임에 해당하는 모든 subject gaze 좌표 목록을 반환한다.

    Returns:
        [(subject_id, [(x_norm, y_norm), ...]), ...] — 정규화된 좌표 (0~1)
    """
    ts_us = int(frame_idx / fps * 1_000_000)
    half = int(1_000_000 / fps / 2)

    result = []
    for zip_path in sorted(gaze_dir.glob("gaze_s*.zip")):
        sid, (w, h), samples = _load_subject_gaze(str(zip_path), clip_id)
        if not samples:
            continue
        points = [
            (x / w, y / h)
            for t, x, y, conf in samples
            if abs(t - ts_us) <= half and conf > 0.5
        ]
        if points:
            result.append((sid, points))
    return result


def overlay_gaze(
    frame_img: Image.Image,
    gaze_points: list[tuple[str, list[tuple[float, float]]]],
) -> Image.Image:
    """frame_img에 subject별 gaze 포인트를 오버레이한다."""
    if not gaze_points:
        return frame_img

    overlay = Image.new("RGBA", frame_img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = frame_img.size

    for i, (sid, points) in enumerate(gaze_points):
        r, g, b = _COLORS[i % len(_COLORS)]
        for nx, ny in points:
            cx, cy = int(nx * w), int(ny * h)
            draw.ellipse(
                [cx - _RADIUS, cy - _RADIUS, cx + _RADIUS, cy + _RADIUS],
                fill=(r, g, b, _ALPHA),
                outline=(255, 255, 255, 200),
                width=1,
            )

    base = frame_img.convert("RGBA")
    combined = Image.alpha_composite(base, overlay)
    return combined.convert("RGB")
