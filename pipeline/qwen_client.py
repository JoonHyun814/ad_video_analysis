"""Qwen2.5-VL 로컬 추론 클라이언트.

init() 한 번 호출 후 infer() 로 재사용한다. 모델은 모듈 레벨 싱글턴으로 캐싱된다.
"""
import json
import re
from pathlib import Path

from PIL import Image

_DEFAULT_MODEL = "unsloth/Qwen2.5-VL-7B-Instruct"

_model = None
_tokenizer = None


def init(model_path: str = _DEFAULT_MODEL, load_in_4bit: bool = True) -> None:
    """모델을 로드하고 추론 모드로 전환한다. lora_path 를 넘기면 어댑터를 자동 인식한다."""
    global _model, _tokenizer
    from unsloth import FastVisionModel

    print(f"  Qwen 모델 로드 중: {model_path}")
    _model, _tokenizer = FastVisionModel.from_pretrained(
        model_name=model_path,
        load_in_4bit=load_in_4bit,
    )
    FastVisionModel.for_inference(_model)
    print("  Qwen 모델 로드 완료")


def infer(image_paths: list[str | Path], prompt: str, max_new_tokens: int = 1024) -> str:
    """이미지(없어도 됨)와 프롬프트로 모델 응답 텍스트를 반환한다."""
    if _model is None:
        raise RuntimeError("qwen_client.init()를 먼저 호출하세요.")

    import torch

    images = [Image.open(p).convert("RGB") for p in image_paths] if image_paths else []

    content = [{"type": "image"} for _ in images]
    content.append({"type": "text", "text": prompt})
    messages = [{"role": "user", "content": content}]

    text = _tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

    if images:
        inputs = _tokenizer(
            images, text, return_tensors="pt", add_special_tokens=False
        ).to("cuda")
    else:
        inputs = _tokenizer(
            text=text, return_tensors="pt", add_special_tokens=False
        ).to("cuda")

    with torch.inference_mode():
        out_ids = _model.generate(
            **inputs, max_new_tokens=max_new_tokens, do_sample=False
        )

    new_ids = out_ids[0][inputs["input_ids"].shape[1]:]
    return _tokenizer.decode(new_ids, skip_special_tokens=True).strip()


def release() -> None:
    """Qwen 모델을 메모리에서 해제한다."""
    global _model, _tokenizer
    _model = None
    _tokenizer = None


def parse_json(text: str) -> dict:
    """응답에서 JSON 객체를 파싱한다. 실패 시 error 키를 포함한 dict를 반환한다."""
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start != -1:
        try:
            return json.loads(text[start:])
        except json.JSONDecodeError:
            pass
    return {"error": "parse_failed", "raw": text[:500]}
