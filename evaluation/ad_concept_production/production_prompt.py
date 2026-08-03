"""scenario_analysis.json → ad_production_reference 용 연출 요소를 추출하는 프롬프트를 만든다.

evaluation/creative/element_analysis.py 와는 별개의 새 프롬프트다 — enum 사전(industry/subtype
어휘)만 evaluation/creative/element_schema.py 를 그대로 참조하고(중복 유지가 아니라 단일
출처를 공유), 프롬프트 문구·조립 로직은 이 파이프라인 전용으로 새로 짰다. 출력 모양은
evaluation/creative/element_vector_store.py 의 upsert_analysis() 가 그대로 소비할 수 있도록
{"profile":{...}, "casting":{...}, "elements":[...]} 형태를 유지한다.
"""
import json

from evaluation.creative import element_schema as es


def _cardinality(etype: str) -> str:
    if etype in es.SINGLE_TYPES:
        return "영상당 정확히 1개"
    if etype in es.NONE_TYPES:
        return "해당하는 만큼 복수(없으면 'none' 1개)"
    return "해당하는 만큼 복수(없으면 생략)"


def _enum_guide(industry: str, secondary: str | None) -> str:
    lines: list[str] = []
    for etype, subtypes in es.subtypes_for(industry, secondary).items():
        lines.append(f"[{etype}] — {_cardinality(etype)}")
        lines += [f"  {name}: {desc}" for name, desc in subtypes.items()]
    return "\n".join(lines)


def _casting_schema(industry: str) -> dict:
    schema = {
        "main_model": "|".join(es.MAIN_MODEL),
        "age_band": "|".join(es.AGE_BAND) + "(인물 미등장 시 null)",
        "wardrobe": "|".join(es.WARDROBE) + "(인물 미등장 시 null)",
        "expression_restraint": "true|false — 절제된 표정(무표정~차분) 기조 여부",
        "secondary_roles": "조연 서술(의료인·연구원 등, 없으면 빈 문자열)",
    }
    if industry == "beauty":
        schema["skin_look"] = "|".join(es.SKIN_LOOK)
        schema["hair"] = "|".join(es.HAIR)
    return schema

_ELEMENT_AXIS_NOTE = (
    "narrative_pattern(훅~클로즈 구조 골격) / persuasion_engine(무엇을 논증하는가) / "
    "narrative_form(어떤 형식으로 전달하는가) / tone_register(카테고리 디폴트 톤 대비 반전 여부) "
    "는 서로 다른 4개 축이다 — 하나로 합치지 말고 각각 독립적으로 판단해 1개씩 출력한다."
)


def _output_schema(industry: str, secondary: str | None) -> dict:
    profile: dict = {
        "industry_category": industry,
        "product_category_norm": "|".join(es.PRODUCT_CATEGORY_NORM[industry]),
        "product_subtype": "|".join(es.PRODUCT_SUBTYPE[industry]),
        "product_category_raw": "제품·서비스 카테고리 한국어 원문(예: 스킨케어(세럼))",
        "target_gender": "|".join(es.TARGET_GENDER),
        "usp_category": "|".join(es.USP_CATEGORY) + " — 핵심 차별화 유형 1개",
        "usp_summary": "핵심 USP 1문장(무엇으로 차별화하는지 구체 서술)",
        "positioning_category": "|".join(es.POSITIONING_CATEGORY) + " — 포지셔닝 전략 1개",
        "price_tier": "|".join(es.PRICE_TIER) + " — 가격대 포지션(불명확하면 unknown)",
        "summary": "세그먼트 검색용 요약 3~4문장(제품·타겟·핵심 메시지·톤앤무드)",
    }
    if secondary:
        profile["industry_secondary"] = secondary
    return {
        "profile": profile,
        "casting": _casting_schema(industry),
        "elements": [{
            "element_type": "|".join(es.ELEMENT_TYPES),
            "element_subtype": "해당 element_type 의 subtype enum 값 하나",
            "cut_refs": [1],
            "description": "요소가 무엇인지 한국어 1~2문장(시각 요소·카피 인용 포함)",
            "production_detail": "몇 번째 컷에서 어떤 촬영기법·편집·사운드로 구현했는지 서술",
        }],
    }


_RULES = (
    "[추출 규칙]\n"
    "- 시나리오에 실제 기술된 내용에만 근거한다. 창작·추정 금지.\n"
    "- opening_hook / casting_direction / narrative_pattern / persuasion_engine / narrative_form /\n"
    "  tone_register 는 각 1개 레코드만 출력한다.\n"
    f"- {_ELEMENT_AXIS_NOTE}\n"
    "- 인물이 등장하지 않으면 casting_direction 은 subtype 'none', casting 의 인물 필드는 null.\n"
    "- sensory_demo_shot / trust_device / cta_device / product_shot 는 해당 요소가 전혀 없으면\n"
    "  subtype 'none' 레코드 1개를 출력한다(관습의 의도적 생략을 집계하기 위함).\n"
    "- color_light_code / copy_device / sound_pattern 은 해당하는 만큼 출력한다.\n"
    "- 같은 subtype 이 여러 컷에 반복되면 레코드 1개에 cut_refs 로 컷 번호를 모은다.\n"
    "- enum 에 없는 유형이면 subtype 'other' 를 쓰고 description 에 유형을 구체적으로 서술한다.\n"
    "- 클리셰인지 아닌지 판정하지 않는다. 요소 사실만 기록한다.\n"
    "- 모든 필드를 빠짐없이 채운다. 첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n"
)


def _condense_scenario(scenario: dict) -> str:
    condensed = {
        "brand": scenario.get("brand", ""),
        "concept": scenario.get("concept", ""),
        "narrative": scenario.get("narrative", ""),
        "key_messages": scenario.get("key_messages", []),
        "production_notes": scenario.get("production_notes", ""),
        "cast": [c.get("description", "")[:200] for c in scenario.get("cast", [])],
        "scenes": [
            {
                "cut_index": s["cut_index"],
                "time": s.get("time", ""),
                "beats": [
                    {"type": b.get("type", ""), "desc": b["description"][:220]}
                    for b in s.get("beats", [])
                    if b.get("description")
                ],
            }
            for s in scenario.get("scenes", [])
        ],
    }
    return json.dumps(condensed, ensure_ascii=False, indent=2)


def build_production_prompt(scenario: dict, industry: str, secondary: str | None = None) -> str:
    """산업/부산업 팩이 반영된 연출 요소 추출 프롬프트를 만든다."""
    industry_desc = f"{industry}+{secondary} 복합 산업" if secondary else f"{industry} 산업"
    return (
        f"너는 광고 크리에이티브 분석 전문가다. 아래 [시나리오]({industry_desc} 광고)에서\n"
        "연출 레퍼런스 검색용 크리에이티브 요소를 [subtype 사전]의 enum 으로 분류해\n"
        "[출력 스키마] JSON 으로 추출하라.\n\n"
        + _RULES
        + f"\n[subtype 사전]\n{_enum_guide(industry, secondary)}\n\n"
        + f"[시나리오]\n{_condense_scenario(scenario)}\n\n"
        + f"[출력 스키마 — 값으로 대체하여 채워라]\n"
        + json.dumps(_output_schema(industry, secondary), ensure_ascii=False, indent=2)
    )
