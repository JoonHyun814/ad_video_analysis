"""v5_m0_m3 brand_research_service — productname/brand 기반 GPT 브랜드 리서치.

원본은 이미 app.services.llm_client 게이트웨이를 거치지 않고 OpenAI API 를 직접 호출한다
(knowledge-only 추론 + Responses API web_search 도구) — 이 파일은 거의 무수정으로 이식했고,
API 키 소스만 app.config.settings.OPENAI_API_KEY 에서 이 프로젝트의 env/api.env 로 바꿨다.

M0~M3 경로에서 실제 쓰이는 3개 함수만 이식(research_reviews_with_web/
research_category_reviews_with_web 은 voc_miner 전용 — orchestrator 의 VoC 마이닝은
M0~M3 범위 밖이라 제외).
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from utils.openai_caller import _load_api_key

from generation.v5_m0_m3.brand_research_prompts import BRAND_RESEARCH_SYSTEM, BRAND_RESEARCH_USER

logger = logging.getLogger(__name__)


def _api_key() -> str:
    import os
    return os.environ.get("OPENAI_API_KEY") or _load_api_key()


async def research_brand(
    productname: str, brand: str = "", industry: str = "", *,
    facts: Optional[list] = None,
) -> dict:
    """제품명/브랜드명/업종 기반으로 GPT (knowledge-only) 가 브랜드 정보 추론. 실패 시 {}."""
    if not (productname or "").strip():
        return {}
    try:
        from openai import AsyncOpenAI

        facts_txt = "\n".join(f"- {f}" for f in (facts or []) if str(f).strip()) \
            or "(상세페이지 사실 없음 — 카테고리 일반론으로 채우지 말고 확실한 것만)"
        user_text = BRAND_RESEARCH_USER.format(
            productname=productname, brand=brand or "(미상)",
            industry=industry or "(미상)", facts=facts_txt,
        )
        client = AsyncOpenAI(api_key=_api_key())
        resp = await client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "system", "content": BRAND_RESEARCH_SYSTEM},
                      {"role": "user", "content": user_text}],
            response_format={"type": "json_object"}, temperature=0.4, max_tokens=2000,
        )
        result = json.loads(resp.choices[0].message.content or "{}")
        if not isinstance(result, dict) or not result:
            logger.warning(f"[brand_research] empty result for product={productname!r}")
            return {}
        return {
            "brand_persona": str(result.get("brand_persona", "") or ""),
            "usp": list(result.get("usp", []) or []),
            "uspvisualcues": list(result.get("uspvisualcues", []) or []),
            "key_features": list(result.get("key_features", []) or []),
            "target_audience": str(result.get("target_audience", "") or ""),
            "competitive_position": str(result.get("competitive_position", "") or ""),
            "research_confidence": str(result.get("research_confidence", "low") or "low"),
        }
    except Exception as e:
        logger.warning(f"[brand_research] failed for product={productname!r}: {e}")
        return {}


_COMPETITOR_WEB_PROMPT = """다음 제품의 실제 경쟁 브랜드를 웹 검색으로 조사하고, 자사 대비 차별점을 도출하세요.

제품명: {productname}
브랜드: {brand}
업종/카테고리: {industry}

수행:
1. 웹 검색으로 같은 목적을 해결하는 직접 경쟁 브랜드 2~3개를 실제로 찾으세요 (실존 브랜드명).
2. 각 경쟁사의 핵심 포지션을 한 줄로 요약하세요.
3. 그 경쟁사들 대비 이 제품만의 진짜 차별점(대안도 가진 범용 강점 제외)을 도출하세요.

오직 아래 JSON 형식으로만 응답하세요. 코드펜스/설명 없이 {{ 로 시작해 }} 로 끝낼 것:
{{
  "competitors": [
    {{"name": "실제 경쟁 브랜드명", "positioning": "한 줄 포지션", "ourdifference": "이 제품이 그 경쟁사 대비 다른 점"}}
  ],
  "competitive_position": "실제 경쟁 구도에서 이 제품의 위치 1~2문장 (경쟁사명 포함)",
  "research_confidence": "high | medium | low"
}}
"""


def _extract_json(raw: str) -> dict:
    """web_search 응답 텍스트에서 순수 JSON 추출 (코드펜스/preamble 제거)."""
    import re as _re
    s = (raw or "").strip()
    if s.startswith("```"):
        s = _re.sub(r"^```(?:json)?\s*", "", s)
        s = _re.sub(r"\s*```\s*$", "", s).strip()
    start, end = s.find("{"), s.rfind("}")
    if start != -1 and end > start:
        s = s[start:end + 1]
    try:
        return json.loads(s)
    except Exception:
        return {}


async def research_brand_with_web(productname: str, brand: str = "", industry: str = "") -> dict:
    """web_search 로 실제 경쟁사를 발굴·비교. 실패 시 {}."""
    if not (productname or "").strip():
        return {}
    try:
        from openai import AsyncOpenAI

        prompt = _COMPETITOR_WEB_PROMPT.format(
            productname=productname, brand=brand or "(미상)", industry=industry or "(미상)")
        client = AsyncOpenAI(api_key=_api_key())
        resp = await client.responses.create(
            model="gpt-5.5", tools=[{"type": "web_search"}], input=prompt)
        result = _extract_json(getattr(resp, "output_text", "") or "")
        if not isinstance(result, dict) or not result:
            logger.warning(f"[brand_research_web] empty result for product={productname!r}")
            return {}
        competitors = []
        for c in (result.get("competitors") or [])[:3]:
            if not isinstance(c, dict):
                continue
            name = str(c.get("name") or "").strip()
            if not name:
                continue
            competitors.append({
                "name": name, "positioning": str(c.get("positioning") or ""),
                "ourdifference": str(c.get("ourdifference") or ""),
            })
        return {
            "competitors": competitors,
            "competitive_position": str(result.get("competitive_position", "") or ""),
            "research_confidence": str(result.get("research_confidence", "medium") or "medium"),
        }
    except Exception as e:
        logger.warning(f"[brand_research_web] failed for product={productname!r}: {e}")
        return {}


_PRODUCT_FROM_URL_WEB_PROMPT = """다음 상품 페이지 URL 은 봇 차단/보안 페이지 때문에 직접 수집이 실패했습니다.
웹 검색으로 이 URL 의 제품을 찾아 제품 정보를 수집하세요.

URL: {sourceurl}
사용자가 입력한 제품 제목: {producttitle}

## 검색 요령
- 1순위: 제품 제목 + 판매처/브랜드 조합으로 검색하세요 (예: "제품제목 올리브영", "제품제목 공식").
- 2순위: URL 전체, 또는 URL 안의 상품번호/식별자(예: goodsNo, productNo, prdNo, 숫자 코드)로 검색하세요.
- 같은 제품이 판매되는 다른 채널(공식몰/오픈마켓/블로그·리뷰 글)의 정보도 활용하세요.
- 제품 제목이 있으면 그 제품군의 정보로 충분합니다(세부 옵션·색상까지 특정 못 해도 됨).
  제목이 "(없음)" 인 경우에만 URL/상품번호로 정확히 특정해야 하며, 못 하면 빈 값을 반환하세요.

## 응답 (JSON 객체 하나만)
{{
  "productname": "제품명 (제품을 특정하지 못하면 빈 문자열)",
  "brand": "브랜드명",
  "category": "카테고리 (예: 뷰티 > 스킨케어)",
  "usplist": ["제품 강점/소구점 (검색 결과 근거)"],
  "facts": ["제품 사실 정보 (용량/성분/가격대/수상/인증 등)"],
  "targethints": ["주 타겟 설명"],
  "sources": ["근거 URL"],
  "research_confidence": "high|medium|low"
}}
- 실제 검색 결과 기반만. 제품을 특정하지 못하면 productname 빈 문자열 + low. 지어내지 마세요."""


async def research_product_from_url_with_web(sourceurl: str, producttitle: str = "") -> dict:
    """크롤 차단된 URL 의 제품 정보를 web_search 로 복구. 실패/제품 미특정 시 {}."""
    if not (sourceurl or "").strip():
        return {}
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=_api_key())
        resp = await client.responses.create(
            model="gpt-5.5", tools=[{"type": "web_search"}],
            input=_PRODUCT_FROM_URL_WEB_PROMPT.format(
                sourceurl=sourceurl.strip(), producttitle=(producttitle or "").strip() or "(없음)"))
        result = _extract_json(getattr(resp, "output_text", "") or "")
        if not isinstance(result, dict) or not str(result.get("productname") or "").strip():
            logger.warning(f"[product_from_url_web] 제품 미특정: {sourceurl}")
            return {}
        out = {
            "productname": str(result.get("productname")).strip(),
            "brand": str(result.get("brand") or "").strip(),
            "category": str(result.get("category") or "").strip(),
            "usplist": [str(u).strip() for u in (result.get("usplist") or []) if str(u).strip()][:10],
            "facts": [str(f).strip() for f in (result.get("facts") or []) if str(f).strip()][:10],
            "targethints": [str(t).strip() for t in (result.get("targethints") or []) if str(t).strip()][:5],
            "sources": [str(s).strip() for s in (result.get("sources") or []) if str(s).strip()][:5],
            "researchconfidence": str(result.get("research_confidence", "low") or "low"),
        }
        logger.info(f"[product_from_url_web] 복구 OK: product={out['productname']!r}")
        return out
    except Exception as e:
        logger.warning(f"[product_from_url_web] failed for {sourceurl}: {type(e).__name__}: {e}")
        return {}
