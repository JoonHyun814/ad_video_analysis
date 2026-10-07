"""Qwen2.5-VL 로컬 모델 래퍼 — 단일·다중 이미지 추론 및 일회성 호출 헬퍼.

모델 경로: env/model.env 의 MODEL_ROOT / <model_name> 또는 호출 시 명시적으로 지정.
환경: TRANSFORMERS_OFFLINE=1 로 강제해 로컬 파일만 사용한다.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

import torch
from PIL import Image

os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
# 어텐션 연산 메모리 단편화 완화
os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")

DEFAULT_MODEL_NAME = "Qwen2.5-VL-7B-Instruct"


def _default_model_path() -> Path:
    """env/model.env 의 MODEL_ROOT 아래 기본 모델 경로를 반환한다."""
    from utils.env_loader import get_model_root
    return get_model_root() / DEFAULT_MODEL_NAME


@dataclass
class InferenceResult:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: float


class QwenVLModel:
    """Qwen2.5-VL 로컬 모델 래퍼. 로드 후 재사용 가능."""

    # 이미지당 최대 픽셀 수 — 기본값을 줄여 어텐션 OOM 방지
    # 512*28*28 ≈ 401k px (≈640×627). 고해상도 프레임에서 비전 토큰 폭발 차단.
    DEFAULT_MIN_PIXELS: int = 256 * 28 * 28
    DEFAULT_MAX_PIXELS: int = 512 * 28 * 28

    def __init__(
        self,
        model_path: str | Path,
        min_pixels: int | None = None,
        max_pixels: int | None = None,
    ) -> None:
        from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

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
            self.model_path, local_files_only=True,
            min_pixels=min_pixels or self.DEFAULT_MIN_PIXELS,
            max_pixels=max_pixels or self.DEFAULT_MAX_PIXELS,
        )
        self.model.eval()

        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
        print(f"모델 로딩 완료: {self.model_name}")

    def infer(self, image: Image.Image, prompt: str, max_new_tokens: int = 32) -> InferenceResult:
        """단일 이미지 + 텍스트 프롬프트 추론."""
        return self.infer_multi([image], prompt, max_new_tokens)

    def infer_multi(
        self, images: list[Image.Image], prompt: str, max_new_tokens: int = 512
    ) -> InferenceResult:
        """다중(또는 0개) 이미지 + 텍스트 프롬프트 추론."""
        content = [{"type": "image", "image": img} for img in images]
        content.append({"type": "text", "text": prompt})
        messages = [{"role": "user", "content": content}]

        text_input = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        if images:
            from qwen_vl_utils import process_vision_info

            image_inputs, _ = process_vision_info(messages)
            inputs = self.processor(
                text=[text_input], images=image_inputs, padding=True, return_tensors="pt"
            ).to(self.model.device)
        else:
            inputs = self.processor(
                text=[text_input], padding=True, return_tensors="pt"
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


def call_qwen_vl(
    prompt: str,
    image_paths: list[str | Path] | None = None,
    model_path: str | Path | None = None,
    max_new_tokens: int = 512,
) -> dict:
    """모델을 일회 로드해 추론하고 {"text": ...} 를 반환한다.

    연속 호출(배치 처리)에는 QwenVLModel 을 직접 생성해 재사용한다.
    """
    if model_path is None:
        model_path = _default_model_path()
    images = [Image.open(p).convert("RGB") for p in (image_paths or [])]
    model = QwenVLModel(model_path)
    result = model.infer_multi(images, prompt, max_new_tokens)
    return {
        "text": result.text,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "latency_ms": result.latency_ms,
    }
