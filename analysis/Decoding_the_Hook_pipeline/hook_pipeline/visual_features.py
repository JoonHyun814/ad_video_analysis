"""프레임 단위 시각적 피처: 채도 평균, 밝기 평균, 시각적 혼잡도(JPEG 압축률).

시각적 혼잡도 정의:
  complexity = JPEG_compressed_bytes / raw_pixel_bytes
  - 높을수록 압축이 덜 됨 → 픽셀 단위 변화량·세부 디테일 정보량이 많음
  - 낮을수록 단순한 배경·대형 단색 영역이 지배적
"""
import io
from pathlib import Path

import numpy as np
from PIL import Image

_JPEG_QUALITY = 85  # 혼잡도 기준 압축률 (변경 시 결과 비교 불가)


def extract_visual_features(frame_paths: list[Path | str]) -> dict[str, float | None]:
    """샘플링 프레임 목록에서 채도·밝기·혼잡도 평균을 계산한다."""
    empty: dict[str, float | None] = {"saturation_mean": None, "brightness_mean": None, "complexity_mean": None}
    if not frame_paths:
        return empty

    saturations, brightnesses, complexities = [], [], []
    for p in frame_paths:
        img = Image.open(p).convert("RGB")
        arr = np.array(img, dtype=np.float32) / 255.0

        v = arr.max(axis=2)
        s = np.where(v > 0, (v - arr.min(axis=2)) / v, 0.0)
        saturations.append(float(s.mean()))
        brightnesses.append(float(v.mean()))
        complexities.append(_jpeg_complexity(img))

    return {
        "saturation_mean": round(float(np.mean(saturations)), 4),
        "brightness_mean": round(float(np.mean(brightnesses)), 4),
        "complexity_mean": round(float(np.mean(complexities)), 4),
    }


def _jpeg_complexity(img: Image.Image) -> float:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=_JPEG_QUALITY)
    return buf.tell() / (img.width * img.height * 3)


def format_for_prompt(vf: dict | None) -> str:
    """visual_features dict → 프롬프트 삽입 텍스트."""
    if not vf or vf.get("saturation_mean") is None:
        return ""
    sat = vf["saturation_mean"]
    bri = vf["brightness_mean"]
    cmp = vf["complexity_mean"]
    return (
        f"Visual Features (averaged over sampled frames):\n"
        f"- Saturation: {sat:.3f} (0=grayscale, 1=fully saturated)\n"
        f"- Brightness: {bri:.3f} (0=dark, 1=bright)\n"
        f"- Visual Complexity: {cmp:.3f} (JPEG compression ratio; higher=more detail/texture)\n"
    )
