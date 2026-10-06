"""FPS 기반 프레임 추출 + VL 추론. motion 도메인은 제외."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import cv2
from PIL import Image

from .model import QwenVLModel
from .prompts import build_multi_prompt, parse_multi_response


def _extract_frames(video_path: Path, fps: float) -> list[tuple[int, float, Image.Image]]:
    """fps 속도로 균등하게 프레임을 추출해 (frame_idx, timestamp, PIL_image) 반환."""
    cap = cv2.VideoCapture(str(video_path))
    video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(round(video_fps / fps)))

    frames: list[tuple[int, float, Image.Image]] = []
    idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if idx % step == 0:
            ts = round(idx / video_fps, 3)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append((idx, ts, Image.fromarray(rgb)))
        idx += 1
    cap.release()
    return frames


def analyze_video(
    video_path: Path,
    model: QwenVLModel,
    target_domains: list[str],
    fps: float = 2.0,
) -> dict[str, Any]:
    """영상을 fps 속도로 분석해 프레임별 태그 및 통계 반환."""
    import psutil

    frames_data = _extract_frames(video_path, fps)
    total = len(frames_data)
    prompt = build_multi_prompt(target_domains)

    result_frames: list[dict[str, Any]] = []
    total_in = total_out = 0
    cpu_samples: list[float] = []
    gpu_samples: list[float] = []
    t_start = time.perf_counter()

    for i, (frame_idx, ts, image) in enumerate(frames_data):
        print(f"  [{i+1}/{total}] frame={frame_idx} t={ts}s", end="\r", flush=True)

        result = model.infer(image, prompt, max_new_tokens=64)
        tags = parse_multi_response(result.text, target_domains)
        total_in  += result.input_tokens
        total_out += result.output_tokens

        cpu_samples.append(psutil.cpu_percent(interval=None))
        gpu_samples.append(model.gpu_util_avg())
        result_frames.append({"frame_idx": frame_idx, "time": ts, "tags": tags})

    elapsed = round(time.perf_counter() - t_start, 2)
    print()

    return {
        "video": str(video_path),
        "fps": fps,
        "target_domains": target_domains,
        "total_frames": total,
        "inference_time_sec": elapsed,
        "tokens_used": {
            "input": total_in,
            "output": total_out,
            "total": total_in + total_out,
        },
        "resource_usage": {
            "gpu_memory_peak_mb": model.gpu_peak_mb(),
            "cpu_percent_avg": round(sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0, 1),
            "gpu_util_avg": round(sum(gpu_samples) / len(gpu_samples) if gpu_samples else 0, 1),
        },
        "frames": result_frames,
    }
