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


def infer(image_paths: list[str | Path], prompt: str, max_new_tokens: int = 4096) -> str:
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
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            repetition_penalty=1.1,  # 반복 억제 → 장황한 중첩 JSON 감소 → 출력 단축
            use_cache=True,
        )

    new_ids = out_ids[0][inputs["input_ids"].shape[1]:]
    return _tokenizer.decode(new_ids, skip_special_tokens=True).strip()


def release() -> None:
    """Qwen 모델을 메모리에서 해제한다."""
    global _model, _tokenizer
    _model = None
    _tokenizer = None


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
                # 중첩 객체/배열의 값 하나가 완전히 닫힘
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

    # 열린 문자열 닫기 (이스케이프 진행 중이면 미완성 이스케이프 제거 후 닫기)
    if in_string:
        if escape:
            candidate = candidate[:-1]  # 미완성 '\' 제거
        candidate += '"'

    # 마지막 불완전 키-값 제거.
    # 값이 문자열("..."), 비문자열(숫자·true 등), 없음 세 가지 모두 처리.
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

    # 닫기 실패 시 안전 지점으로 후퇴
    for pos in (depth1_safe, last_safe):
        if pos > 0:
            try:
                return json.loads(text[:pos])
            except json.JSONDecodeError:
                continue
    return None
