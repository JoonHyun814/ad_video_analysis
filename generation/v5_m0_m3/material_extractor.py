"""v5_m0_m3 material_extractor — v1 analysis dict → ProductInfoCard 매핑.

원본에서 persona_v2 보강 블록(gpt_json.gpt_chat_json)은 제외했다 — 그 함수는 소스 프로젝트의
"prompts" DB 테이블에서 편집 가능한 시스템 프롬프트를 읽어오는 게 유일한 경로였고 코드 폴백이
없다. 사용자가 승인한 DB 접근 범위는 카테고리 분류 테이블(read-only)뿐이라 이 기능은 이식하지
않았다 — personas 는 빈 리스트로 남고 그만큼 targethints 근거가 줄어든다(module0_ingest 는
card.targetaudience/heropersonabrief 로 계속 동작).
usp_score_service.score_usps(5축 가점)는 module0_ingest 가 uspscoring=False 로 호출해
M0~M3 경로에서 실행되지 않으므로 이식하지 않았다.
"""
from __future__ import annotations

import logging
from typing import Any

from generation.v5_m0_m3 import brand_research_service, v1_bridge
from generation.v5_m0_m3.product_classifier import classify_by_rule
from generation.v5_m0_m3.schemas import ProductInfoCard

logger = logging.getLogger(__name__)


def _trim_persona(p: dict) -> dict:
    if not isinstance(p, dict):
        return {}
    return {
        "rank": p.get("rank") or "",
        "label": p.get("label") or "",
        "agerange": p.get("age_range") or p.get("agerange") or "",
        "coredesire": p.get("core_desire") or p.get("coredesire") or "",
        "isprimary": bool(p.get("is_primary") if "is_primary" in p else p.get("isprimary")),
    }


def _merge_keypoints(*sources: list) -> list[str]:
    """여러 source list 를 keypoints 로 union + de-dup (대소문자/공백 normalize)."""
    seen: set[str] = set()
    out: list[str] = []
    for src in sources:
        if not src:
            continue
        for item in src:
            if not isinstance(item, str):
                continue
            s = item.strip()
            if not s:
                continue
            key = s.lower().replace(" ", "")
            if key in seen:
                continue
            seen.add(key)
            out.append(s)
    return out


def map_v1_to_card(v1_dict: dict[str, Any]) -> ProductInfoCard:
    """v1 analysis dict → ProductInfoCard. 분류기 결과 자동 합성."""
    cls = classify_by_rule(v1_dict)

    payload: dict[str, Any] = {
        "productname": v1_dict.get("productname") or "",
        "brand": v1_dict.get("brand") or "",
        "category2id": v1_dict.get("category2id") or "",
        "category2name": v1_dict.get("category2name") or "",
        "category3id": v1_dict.get("category3id") or "",
        "category3name": v1_dict.get("category3name") or "",
        "categorypath": v1_dict.get("categorypath") or "",
        "industry": v1_dict.get("industry") or "",
        "subcategory": v1_dict.get("subcategory") or "",
        "adheadline": v1_dict.get("adheadline") or "",
        "functionalstrengths": [],
        "productfeatures": v1_dict.get("productfeatures") or "",
        "targetaudience": v1_dict.get("targetaudience") or "",
        "tone": v1_dict.get("tone") or "",
        "keypoints": _merge_keypoints(
            v1_dict.get("keypoints") or [], v1_dict.get("functionalstrengths") or [],
            v1_dict.get("key_features") or [],
        ),
        "style": v1_dict.get("style") or "",
        "productimageurls": v1_dict.get("productimageurls") or [],
        "brandlogourl": v1_dict.get("brandlogourl"),
        "imagedescurlmap": v1_dict.get("imagedescurlmap") or {},
        "imagetypeurlmap": v1_dict.get("imagetypeurlmap") or {},
        "confidence": float(v1_dict.get("confidence") or 0.0),
        "brandpersona": v1_dict.get("brand_persona"),
        "usp": v1_dict.get("usp") or [],
        "uspvisualcues": v1_dict.get("uspvisualcues") or [],
        "competitiveposition": v1_dict.get("competitive_position"),
        "competitors": v1_dict.get("competitors") or [],
        "researchconfidence": v1_dict.get("research_confidence"),
        "personas": [_trim_persona(p) for p in (v1_dict.get("personas_v2") or []) if p],
        "primarypersonaid": v1_dict.get("primary_persona_id"),
        "heropersonabrief": v1_dict.get("hero_persona_brief"),
        "producttype": cls["producttype"],
        "involvementlevel": cls["involvementlevel"],
        "visibility": cls.get("visibility", ""),
        "benefittype": cls.get("benefittype", ""),
        "producttype7": cls.get("producttype7", ""),
        "classifierconfidence": cls["classifierconfidence"],
        "visualmotifs": v1_dict.get("visualmotifs") or [],
        "scenariojtbd": v1_dict.get("scenariojtbd") or [],
        "negativecues": v1_dict.get("negativecues") or [],
        "materialspecs": v1_dict.get("materialspecs"),
    }
    return ProductInfoCard(**payload)


async def extract_via_v1(
    *, gpt_texts: list[str], competitorresearch: bool = False,
) -> ProductInfoCard:
    """텍스트 소재 → GPT 분석 → brand_research 보강 → ProductInfoCard.

    원본은 첨부 이미지도 함께 vision 분석했지만, module0_ingest.ingest() 는 URL 크롤 텍스트만
    넘기고 이미지는 항상 빈 리스트였다(M0 는 URL 인제스트 전용, 파일 업로드 경로 없음) — 그래서
    이미지 인자를 아예 제거했다.
    """
    combined_text = "\n\n---\n\n".join(gpt_texts) if gpt_texts else ""
    analysis: dict = {}
    if combined_text:
        user_content: list[dict] = [{
            "type": "text",
            "text": f"다음 소재를 분석해주세요:\n\n{combined_text}",
        }]
        system_prompt = v1_bridge.get_analysis_prompt()
        analysis = await v1_bridge.analyze_material(system_prompt, user_content)

    analysis = category_lookup_enrich(analysis)

    # brand_research (knowledge-only)
    try:
        productname = analysis.get("productname") or ""
        brand = analysis.get("brand") or ""
        industry = analysis.get("industry") or analysis.get("category") or ""
        if productname:
            facts_in = list(analysis.get("keypoints") or [])
            if analysis.get("productfeatures"):
                facts_in.append(str(analysis["productfeatures"]))
            br_result = await brand_research_service.research_brand(
                productname=productname, brand=brand, industry=industry, facts=facts_in)
            if br_result:
                for k in ("brand_persona", "usp", "uspvisualcues", "key_features",
                          "target_audience", "competitive_position", "research_confidence"):
                    if br_result.get(k):
                        analysis[k] = br_result[k]
    except Exception as e:
        logger.warning(f"[material_extractor] brand_research merge skip: {e}")

    # M2 진짜 경쟁사 비교 — competitorresearch 옵션 ON 일 때만 web_search.
    if competitorresearch:
        try:
            pn = analysis.get("productname") or ""
            if pn:
                cw = await brand_research_service.research_brand_with_web(
                    productname=pn, brand=analysis.get("brand") or "",
                    industry=analysis.get("industry") or analysis.get("category") or "")
                if cw.get("competitors"):
                    analysis["competitors"] = cw["competitors"]
                    if cw.get("competitive_position"):
                        analysis["competitive_position"] = cw["competitive_position"]
        except Exception as e:
            logger.warning(f"[material_extractor] competitor web research skip: {e}")

    analysis["productimageurls"] = []
    return map_v1_to_card(analysis)


def category_lookup_enrich(analysis: dict) -> dict:
    """v1_bridge.get_analysis_prompt() 가 준 category3id 를 2depth 정보로 보강."""
    from generation.v5_m0_m3.category_lookup import enrich_category
    return enrich_category(analysis)
