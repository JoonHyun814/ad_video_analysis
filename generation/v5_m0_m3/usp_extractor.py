"""v5_m0_m3 usp_extractor — USP(핵심 메시지 한 문장) 도출.

원본에서 M0 인제스트가 실제 호출하는 extract() 경로만 이식(3안 다양화 extract_variants 는
M0~M3 경로 미사용이라 제외). llm_chat → llm_adapter.chat_json 으로 교체.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from generation.v5_m0_m3 import llm_adapter, narrative_docs
from generation.v5_m0_m3.schemas import ProductInfoCard, ProductType, USPResult

logger = logging.getLogger(__name__)

_FOCUS_INSTRUCTIONS: dict[ProductType, str] = {
    ProductType.SINGLEPRODUCT: "이 제품만의 차별화 포인트를 한 문장으로. 기능/성분/효과 중 가장 강한 것 하나.",
    ProductType.PRODUCTLINE: "라인업 전체의 공통 가치를 한 문장으로. 개별 SKU 가 아니라 라인 전체.",
    ProductType.DIGITALPRODUCT: "해결하는 핵심 문제 + 결과 지표를 한 문장으로. ROI 가능하면 수치 포함.",
    ProductType.INTANGIBLESERVICE: "고객이 얻는 구체적 혜택과 수치를 한 문장으로. 결과 변화 중심.",
    ProductType.PLATFORM: "플랫폼의 편의성/선택지/연결 가치를 한 문장으로.",
    ProductType.BRAND: "브랜드 세계관/슬로건을 한 문장으로. 특정 제품 기능 아님.",
}

_LLM_SYSTEM_PROMPT_BASE = """당신은 광고 카피 디렉터입니다.
주어진 제품 정보(ProductInfoCard) + 첨부된 광고 가이드를 종합해 USP(핵심 메시지)를 한 문장으로 도출하세요.

[경쟁 대안 대비 — USP 도출 전 반드시 먼저 수행]
1. payload 에 competitors(실제 경쟁사 목록)가 있으면 가정하지 말고 그 실제 경쟁사명을 기준으로 삼아라. 없을 때만 직접/간접 대안을 가정하라.
2. 그 경쟁사/대안들도 똑같이 가진 속성(범용 강점: "간편함", "믿을 수 있는", "데일리로 좋은" 등 누구나 하는 말)은 USP 후보에서 제외하라.
3. 남은 "경쟁사 대비 우리 제품만의 차별점"만으로 USP 를 만들어라.
4. competitivealternative 에는 실제 경쟁사(있으면)나 가정한 대안을 적어라.

규칙:
- USP 는 15초 영상의 tagline(광고 카피 핵심) 으로 그대로 쓸 수 있어야 합니다.
- 25자 이내. 간결하고 임팩트 있게.
- 추상어("최고", "최선") 금지. 구체적 수치/결과/차별점 우선.
- 사용자 제품에만 해당하는 차별점이어야 합니다.

JSON 으로만 응답 (competitivealternative 필드는 반드시 채울 것, null 금지):
{
  "text": "USP 한 문장 (25자 이내)",
  "alternatives": ["대안 1", "대안 2"],
  "reasoning": "왜 이 USP 가 가장 강한지 한 줄 근거",
  "competitivealternative": "가정한 직접/간접 경쟁 대안 한 줄"
}
"""


def _extract_from_existing(card: ProductInfoCard) -> USPResult | None:
    """productcard.usp 에 이미 USP 가 있으면 첫 번째를 채택. 없으면 None."""
    candidates = [s.strip() for s in (card.usp or []) if isinstance(s, str) and s.strip()]
    if not candidates:
        return None
    return USPResult(
        text=candidates[0], alternatives=candidates[1:], source="productcardusp",
        reasoning="brand_research_service 단계에서 이미 도출된 USP 를 채택.",
    )


def _build_user_payload(card: ProductInfoCard) -> dict[str, Any]:
    focus = _FOCUS_INSTRUCTIONS.get(card.producttype, _FOCUS_INSTRUCTIONS[ProductType.SINGLEPRODUCT])
    return {
        "producttype": card.producttype.value,
        "involvementlevel": card.involvementlevel.value,
        "productname": card.productname,
        "brand": card.brand,
        "category2name": card.category2name,
        "category3name": card.category3name,
        "productfeatures": (card.productfeatures or "")[:500],
        "functionalstrengths": card.functionalstrengths,
        "keypoints": card.keypoints,
        "targetaudience": card.targetaudience,
        "adheadline": card.adheadline,
        "personas": card.personas[:2] if card.personas else [],
        "heropersonabrief": card.heropersonabrief,
        "competitors": card.competitors[:3] if card.competitors else [],
        "focusinstruction": focus,
    }


async def extract_with_llm(card: ProductInfoCard) -> USPResult:
    """LLM 으로 USP 도출. narrative_picker 자료 inject."""
    docs = narrative_docs.load_for_module("narrative_picker")
    payload = _build_user_payload(card)
    system_prompt = _LLM_SYSTEM_PROMPT_BASE + "\n\n---\n\n" + docs

    try:
        data = await asyncio.to_thread(
            llm_adapter.chat_json, system_prompt, json.dumps(payload, ensure_ascii=False))
    except Exception as e:
        logger.warning(f"LLM USP extract failed, fallback to adheadline: {e}")
        return USPResult(
            text=card.adheadline or card.productname or "", alternatives=[], source="llm",
            reasoning=f"LLM 실패 fallback: {type(e).__name__}",
        )

    return USPResult(
        text=str(data.get("text") or ""),
        alternatives=[str(a) for a in (data.get("alternatives") or [])][:3],
        source="llm",
        reasoning=str(data.get("reasoning") or ""),
        competitivealternative=str(data.get("competitivealternative") or ""),
    )


async def extract(card: ProductInfoCard) -> USPResult:
    """USP 도출 진입점. 기존 USP 우선, 없으면 LLM."""
    existing = _extract_from_existing(card)
    if existing is not None:
        return existing
    return await extract_with_llm(card)
