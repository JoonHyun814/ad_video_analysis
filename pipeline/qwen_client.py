"""Qwen2.5-VL vLLM 추론 클라이언트.

init() 한 번 호출 후 infer() 로 재사용한다. 모델은 모듈 레벨 싱글턴으로 캐싱된다.
"""
import json
import re
from pathlib import Path

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


def parse_json(text: str) -> dict:
    """응답에서 JSON 객체를 파싱한다. 잘린 JSON은 복구를 시도하고, 실패 시 error 키를 반환한다."""
    text = re.sub(r"```(?:json)?\s*", "", text).strip()

    start = text.find("{")
    if start == -1:
        return {"error": "parse_failed", "raw": text[:500]}
    text = text[start:]

    # 1) 완전한 JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2) JSON 뒤에 설명 텍스트가 붙은 경우 — 첫 완전한 객체만 추출
    try:
        obj, _ = json.JSONDecoder().raw_decode(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # 3) 토큰 한도로 잘린 경우 — 괄호 보충해 복구
    repaired = _repair_json(text)
    if repaired is not None:
        return repaired

    return {"error": "parse_failed", "raw": text[:500]}


def _repair_json(text: str) -> dict | None:
    """잘린 JSON에 닫는 괄호를 보충해 복구한다. 복구 불가 시 None 반환."""
    stack: list[str] = []
    in_string = False
    escape = False
    last_safe = 0       # 최상위 객체 완전 종료 위치
    depth1_safe = 0     # depth=1 에서 값이 완전히 닫힌 마지막 위치

    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()
            depth = len(stack)
            if depth == 0:
                last_safe = i + 1
            elif depth == 1 and ch == "}":
                depth1_safe = i + 1

    if not stack and not in_string:
        for pos in (last_safe, depth1_safe):
            if pos > 0:
                try:
                    return json.loads(text[:pos])
                except json.JSONDecodeError:
                    continue
        return None

    candidate = text.rstrip()

    if in_string:
        if escape:
            candidate = candidate[:-1]
        candidate += '"'

    _STR = r'"(?:[^"\\]|\\.)*"'
    _NONSTR = r'[^,}\]"\\]*'
    candidate = re.sub(
        rf',\s*{_STR}(?:\s*:\s*(?:{_STR}|{_NONSTR}))?$',
        "",
        candidate.rstrip(),
        flags=re.DOTALL,
    )
    candidate = candidate.rstrip().rstrip(",")

    closing = "".join("}" if c == "{" else "]" for c in reversed(stack))

    try:
        return json.loads(candidate + closing)
    except json.JSONDecodeError:
        pass

    for pos in (depth1_safe, last_safe):
        if pos > 0:
            try:
                return json.loads(text[:pos])
            except json.JSONDecodeError:
                continue
    return None
