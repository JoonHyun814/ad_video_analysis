"""Qwen2.5-VL 로컬 모델 로더 및 단일 프레임 추론.

환경: C:\\Users\\llm\\workspace\\.venv-train
모델 경로: D:\\models\\<model-name>
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

import torch
from PIL import Image

# 로컬 모델 경로를 HF Hub repo ID로 검증하지 않도록 오프라인 모드 강제
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")


@dataclass
class InferenceResult:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: float


class QwenVLModel:
    """Qwen2.5-VL 모델 래퍼. 로드 후 재사용 가능."""

    def __init__(self, model_path: str | Path) -> None:
        from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor

        self.model_path = str(model_path)
        self.model_name = Path(model_path).name

        print(f"모델 로딩: {self.model_path}")
        self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            self.model_path,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            local_files_only=True,
        )
        self.processor = AutoProcessor.from_pretrained(
            self.model_path, local_files_only=True
        )
        self.model.eval()

        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
        print(f"모델 로딩 완료: {self.model_name}")

    def infer(self, image: Image.Image, prompt: str, max_new_tokens: int = 32) -> InferenceResult:
        """단일 이미지 + 텍스트 프롬프트 추론."""
        from qwen_vl_utils import process_vision_info

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        text = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        image_inputs, _ = process_vision_info(messages)
        inputs = self.processor(
            text=[text], images=image_inputs, padding=True, return_tensors="pt"
        ).to(self.model.device)

        input_len = inputs.input_ids.shape[1]
        t0 = time.perf_counter()
        with torch.no_grad():
            output_ids = self.model.generate(**inputs, max_new_tokens=max_new_tokens)
        latency_ms = (time.perf_counter() - t0) * 1000

        trimmed = output_ids[0][input_len:]
        output_text = self.processor.decode(trimmed, skip_special_tokens=True)

        return InferenceResult(
            text=output_text.strip(),
            input_tokens=input_len,
            output_tokens=int(len(trimmed)),
            latency_ms=round(latency_ms, 1),
        )

    def gpu_peak_mb(self) -> float:
        if torch.cuda.is_available():
            return round(torch.cuda.max_memory_allocated() / 1024**2, 1)
        return 0.0

    def gpu_util_avg(self) -> float:
        """현재 GPU utilization (%) — pynvml 없으면 0 반환."""
        try:
            import pynvml
            pynvml.nvmlInit()
            h = pynvml.nvmlDeviceGetHandleByIndex(0)
            return float(pynvml.nvmlDeviceGetUtilizationRates(h).gpu)
        except Exception:
            return 0.0
