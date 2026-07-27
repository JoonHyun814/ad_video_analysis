"""product_name(+선택 힌트)을 웹검색 기반 LLM 조사로 category/usp/target 프로필을 만든다."""
import json

from utils.llm_caller import call_claude

_SCHEMA = json.dumps({
    "category": "산업·제품 카테고리 (한국어 2줄 이내: 산업 카테고리 + 제품 카테고리)",
    "usp": "핵심 차별화 포인트 (한국어 1~2문장)",
    "target": "타겟 페르소나 (한국어 1~2문장, 연령대·성별·라이프스타일 포함)",
}, ensure_ascii=False, indent=2)


def _known_block(category: str | None, usp: str | None, target: str | None) -> str:
    known = [
        f"- {label}(확정, 그대로 사용): {val}"
        for label, val in (("카테고리", category), ("USP", usp), ("타겟", target))
        if val
    ]
    if not known:
        return ""
    return "\n\n[이미 확정된 정보 — 그대로 반영하고 나머지만 조사]\n" + "\n".join(known)


def build_research_prompt(product_name: str, category: str | None, usp: str | None, target: str | None) -> str:
    """웹검색 기반 마케팅 프로필 조사 프롬프트를 만든다."""
    return (
        f"'{product_name}' 브랜드/제품을 웹 검색으로 조사해 마케팅 프로필을 JSON으로 추출하라.\n"
        "실제 검색 결과에 근거해 작성하고, 확인되지 않는 내용은 추측하지 말고 조사된 사실 위주로 서술하라.\n"
        "첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n"
        f"{_known_block(category, usp, target)}\n\n"
        f"[출력 스키마]\n{_SCHEMA}"
    )


def research_product(
    product_name: str,
    category: str | None = None,
    usp: str | None = None,
    target: str | None = None,
    timeout: int = 300,
) -> dict:
    """product_name을 조사해 category/usp/target 프로필을 만든다.

    세 값을 사용자가 모두 지정했으면 조사 없이 그대로 반환한다.
    일부만 지정했으면 나머지만 웹검색으로 보완한다 (지정값은 덮어쓰지 않음).
    """
    if category and usp and target:
        return {"category": category, "usp": usp, "target": target}
    result = call_claude(
        build_research_prompt(product_name, category, usp, target),
        timeout=timeout,
        allowed_tools=["WebSearch"],
    )
    if "error" in result:
        return result
    return {
        "category": category or result.get("category", ""),
        "usp": usp or result.get("usp", ""),
        "target": target or result.get("target", ""),
    }
