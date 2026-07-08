"""새 컨셉 파이프라인 CM1 — 상품 특징·시장 반응을 분석해 industry_category/product_category 를 결정한다."""
import json

from utils.llm_dispatch import call_llm

_INDUSTRY = "beauty|food_beverage|retail_ecommerce|finance|healthcare|fashion|tech_electronics|automotive|entertainment|travel|education|gaming|other"

_SCHEMA = (
    '{"product_features": ["핵심 제품 특징 (3~5개)"],'
    ' "market_reaction": {'
    '   "positive_signals": ["긍정적 시장 반응·트렌드"],'
    '   "negative_signals": ["부정적 반응·우려·불만"]'
    ' },'
    f' "industry_category": "{_INDUSTRY}",'
    ' "product_category": "제품 카테고리 명칭 (한국어, 예: 스킨케어, 음료, 쇼핑몰, 금융서비스)"}'
)


def build_prompt(brief: dict) -> str:
    """브리프에서 CM1 카테고리 인사이트 프롬프트를 만든다."""
    brief_text = json.dumps(brief, ensure_ascii=False, indent=2)
    return (
        "너는 시장 조사·카테고리 분류 전문가다.\n"
        "아래 브리프의 브랜드·제품을 분석해 제품 특징과 예상 시장 반응을 정리하고, "
        "가장 적합한 industry_category/product_category 를 결정해라.\n\n"
        "분석 항목:\n"
        "1. product_features: 소비자가 체감할 핵심 제품 특징 3~5개\n"
        "2. market_reaction: 이 제품·유사 제품에 대한 시장의 긍정/부정 반응 신호\n"
        "3. industry_category: 아래 enum 중 하나\n"
        "4. product_category: 한국어 제품 카테고리 명칭 하나\n\n"
        "첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
        f"[브리프]\n{brief_text}\n\n"
        f"[출력 스키마]\n{_SCHEMA}"
    )


def run(
    brief: dict,
    *,
    backend: str = "claude",
    gemini_model: str = "",
    codex_model: str | None = None,
) -> dict:
    """브리프에서 산업/제품 카테고리(CM1)를 결정한다."""
    return call_llm(build_prompt(brief), backend=backend, gemini_model=gemini_model, codex_model=codex_model)
