"""Qwen2.5-VL vLLM 추론 클라이언트.

init() 한 번 호출 후 infer() 로 재사용한다. 모델은 모듈 레벨 싱글턴으로 캐싱된다.
"""
import json
from pathlib import Path

from utils.json_utils import parse_json

from PIL import Image

_DEFAULT_MODEL = "unsloth/Qwen2.5-VL-7B-Instruct"

_llm = None
_processor = None
_lora_path: str | None = None


def init(model: str = _DEFAULT_MODEL, lora_path: str | None = None, load_in_4bit: bool = True) -> None:
    """vLLM LLM 인스턴스를 초기화한다.

    model: 베이스 모델명 또는 경로.
    lora_path: 학습된 LoRA 어댑터 경로. None 이면 베이스 모델만 사용한다.
    load_in_4bit 는 호환성 유지를 위해 수용하지만 무시된다.
    """
    global _llm, _processor, _lora_path

    from vllm import LLM
    from transformers import AutoProcessor

    _lora_path = lora_path
    enable_lora = lora_path is not None

    if enable_lora:
        print(f"  LoRA 어댑터 적용: base={model}, lora={lora_path}")
    print(f"  vLLM 모델 로드 중: {model}")

    kwargs = dict(
        model=model,
        dtype="bfloat16",
        max_model_len=8192,
        limit_mm_per_prompt={"image": 30},
        gpu_memory_utilization=0.92,
        enforce_eager=True,          # CUDA graph 비활성 → ~1-2GB 절약
        # 이미지 1장당 최대 128 tile(≈128 토큰)로 제한 → ViT 메모리 절약
        mm_processor_kwargs={"min_pixels": 4 * 28 * 28, "max_pixels": 128 * 28 * 28},
        trust_remote_code=True,
    )
    if enable_lora:
        kwargs["enable_lora"] = True
        kwargs["max_lora_rank"] = 64

    _llm = LLM(**kwargs)
    _processor = AutoProcessor.from_pretrained(model, trust_remote_code=True)
    print("  vLLM 모델 로드 완료")


def infer(image_paths: list[str | Path], prompt: str, max_new_tokens: int = 4096) -> str:
    """이미지(없어도 됨)와 프롬프트로 모델 응답 텍스트를 반환한다."""
    if _llm is None:
        raise RuntimeError("qwen_client.init()를 먼저 호출하세요.")

    from vllm import SamplingParams
    from vllm.lora.request import LoRARequest

    images = [Image.open(p).convert("RGB") for p in image_paths] if image_paths else []

    content = [{"type": "image"} for _ in images]
    content.append({"type": "text", "text": prompt})
    messages = [{"role": "user", "content": content}]

    text = _processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

    sampling_params = SamplingParams(
        temperature=0,
        max_tokens=max_new_tokens,
        repetition_penalty=1.1,
    )

    mm_data = {"image": images} if images else {}

    generate_kwargs = dict(
        prompts=[{"prompt": text, "multi_modal_data": mm_data}],
        sampling_params=sampling_params,
    )
    if _lora_path:
        generate_kwargs["lora_request"] = LoRARequest("ad_lora", 1, _lora_path)

    outputs = _llm.generate(**generate_kwargs)
    return outputs[0].outputs[0].text.strip()


def release() -> None:
    """vLLM 인스턴스를 메모리에서 해제한다."""
    global _llm, _processor, _lora_path
    _llm = None
    _processor = None
    _lora_path = None


__all__ = ["parse_json"]
