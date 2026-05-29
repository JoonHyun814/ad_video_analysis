"""인터넷 검색 기반 광고 브리프 생성."""
import json
import subprocess
import tempfile
import time
from pathlib import Path

from utils.json_utils import parse_json as _parse_json

from evaluation.schemas import _BRIEF_SCHEMA
from generation.web_searcher import search_brand_product

_RETRY_DELAYS = (30, 60, 120)


def generate_brief_from_web(
    brand: str,
    product: str,
    *,
    usp: str = "",
    target_age: str = "",
    target_persona: str = "",
    positioning: str = "",
    slogan: str = "",
    ingredients: list[str] | None = None,
    functions: list[str] | None = None,
    llm_backend: str = "claude",
    codex_model: str | None = None,
) -> dict:
    """웹 검색 결과 기반으로 브리프를 생성한다. 사용자 입력값은 우선 적용한다."""
    user_inputs = _collect_user_inputs(
        brand, product, usp, target_age, target_persona, positioning, slogan, ingredients, functions
    )
    print("  웹 검색 중...")
    search_context = search_brand_product(brand, product)
    prompt = _build_prompt(search_context, user_inputs)
    print(f"  브리프 생성 중 [{llm_backend}]...")
    if llm_backend == "codex":
        result = _call_codex(prompt, model=codex_model)
    else:
        result = _call_claude(prompt)
    return _override_user_inputs(result, user_inputs)


def _collect_user_inputs(
    brand: str,
    product: str,
    usp: str,
    target_age: str,
    target_persona: str,
    positioning: str,
    slogan: str,
    ingredients: list[str] | None,
    functions: list[str] | None,
) -> dict:
    inputs: dict = {"brand": brand, "product": product}
    if usp:
        inputs["usp"] = usp
    if target_age:
        inputs["target_age"] = target_age
    if target_persona:
        inputs["target_persona"] = target_persona
    if positioning:
        inputs["positioning"] = positioning
    if slogan:
        inputs["slogan"] = slogan
    if ingredients:
        inputs["ingredients"] = ingredients
    if functions:
        inputs["functions"] = functions
    return inputs


def _build_prompt(search_context: str, user_inputs: dict) -> str:
    fixed = {k: v for k, v in user_inputs.items() if k not in ("brand", "product")}
    fixed_note = ""
    if fixed:
        fixed_note = (
            "\n[사용자 지정 필드 — 반드시 아래 값을 그대로 사용]\n"
            + json.dumps(fixed, ensure_ascii=False, indent=2)
            + "\n"
        )
    return (
        "너는 광고 기획 전문가다. 아래 웹 검색 결과를 바탕으로 광고 브리프를 작성하라.\n"
        "추론이 불가능한 필드는 빈 문자열 또는 빈 배열로 둔다.\n"
        "첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n"
        f"{fixed_note}"
        f"\n[브랜드] {user_inputs['brand']} / [제품] {user_inputs['product']}\n\n"
        f"[웹 검색 결과]\n{search_context}\n\n"
        f"[출력 스키마]\n{_BRIEF_SCHEMA}"
    )


def _override_user_inputs(generated: dict, user_inputs: dict) -> dict:
    """생성 결과 위에 사용자 입력값을 덮어써 우선 적용한다."""
    for k, v in user_inputs.items():
        generated[k] = v
    return generated


def _call_codex(prompt: str, model: str | None = None) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        out_file = Path(f.name)
    cmd = ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", "-o", str(out_file)]
    if model:
        cmd += ["-m", model]
    cmd.append(prompt)
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    return _parse_json(out_file.read_text(encoding="utf-8"))


def _call_claude(prompt: str) -> dict:
    cmd = ["claude", "-p", prompt]
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as f:
        out_path = Path(f.name)
    text = ""
    for attempt, delay in enumerate((*_RETRY_DELAYS, None), start=1):
        with open(out_path, "w", encoding="utf-8") as out_f:
            subprocess.run(cmd, stdout=out_f, stderr=subprocess.DEVNULL, timeout=300)
        text = out_path.read_text(encoding="utf-8")
        if "529" not in text and "Overloaded" not in text:
            return _parse_json(text)
        if delay is None:
            break
        print(f"      API 과부하(529), {delay}초 후 재시도 ({attempt}/{len(_RETRY_DELAYS)})...")
        time.sleep(delay)
    return _parse_json(text)

