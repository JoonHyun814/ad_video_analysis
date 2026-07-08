"""새 컨셉 파이프라인 CM2 — 유사 상품의 시장 분석으로 target_persona/usp/positioning 을 결정한다."""
import json

from utils.llm_dispatch import call_llm

_SCHEMA = (
    '{"similar_products_analysis": ["유사·경쟁 상품이 시장에서 소구하는 방식 (2~4개)"],'
    ' "target_persona": "타겟 소비자 설명 (연령대·성별·라이프스타일·관심사·구매 동기 포함, 2~3문장)",'
    ' "usp": "유사 상품 대비 차별화 포인트 한 문장",'
    ' "positioning": "브랜드/제품 포지셔닝 (1문장)"}'
)


def build_prompt(brief: dict, cm1: dict) -> str:
    """브리프+CM1 카테고리 인사이트에서 CM2 타겟/포지셔닝 프롬프트를 만든다."""
    brief_text = json.dumps(brief, ensure_ascii=False, indent=2)
    cm1_text = json.dumps(cm1, ensure_ascii=False, indent=2)
    return (
        "너는 브랜드 전략·타겟 분석 전문가다.\n"
        "아래 브리프와 CM1 카테고리 분석을 바탕으로 유사·경쟁 상품들의 시장을 분석하고, "
        "타겟 페르소나·USP·포지셔닝을 결정해라.\n\n"
        "분석 항목:\n"
        "1. similar_products_analysis: 같은 카테고리 유사·경쟁 제품의 시장 소구 방식 2~4개\n"
        "2. target_persona: 이 제품이 실제로 소구해야 할 타겟 소비자\n"
        "3. usp: 유사 제품 대비 차별화 포인트\n"
        "4. positioning: 브랜드/제품 포지셔닝 한 문장\n\n"
        "첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
        f"[브리프]\n{brief_text}\n\n"
        f"[CM1 카테고리 분석]\n{cm1_text}\n\n"
        f"[출력 스키마]\n{_SCHEMA}"
    )


def run(
    brief: dict,
    cm1: dict,
    *,
    backend: str = "claude",
    gemini_model: str = "",
    codex_model: str | None = None,
) -> dict:
    """브리프+CM1로 타겟/USP/포지셔닝(CM2)을 결정한다."""
    return call_llm(build_prompt(brief, cm1), backend=backend, gemini_model=gemini_model, codex_model=codex_model)
