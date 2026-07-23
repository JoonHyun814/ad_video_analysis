"""scenario_analysis.json 에서 클리셰 분석용 크리에이티브 요소를 추출한다 (claude 백엔드).

v2: industry_category 에 따라 subtype 팩을 병합한 enum 가이드로 프롬프트를 조립한다.
"""
import json
import re

from utils.llm_caller import call_claude

from evaluation.creative import element_schema as es


def _cardinality(etype: str) -> str:
    if etype in es.SINGLE_TYPES:
        return "영상당 정확히 1개"
    if etype in es.NONE_TYPES:
        return "해당하는 만큼 복수 (없으면 'none' 1개)"
    return "해당하는 만큼 복수 (없으면 생략)"


def _enum_guide(industry: str, secondary: str | None = None) -> str:
    """주/부 산업 팩이 병합된 element_type 별 subtype enum 가이드를 만든다."""
    lines: list[str] = []
    for etype, subtypes in es.subtypes_for(industry, secondary).items():
        lines.append(f"[{etype}] — {_cardinality(etype)}")
        lines += [f"  {name}: {desc}" for name, desc in subtypes.items()]
    return "\n".join(lines)


def _casting_schema(industry: str) -> dict:
    schema = {
        "main_model": "|".join(es.MAIN_MODEL),
        "age_band": "|".join(es.AGE_BAND) + " (인물 미등장 시 null)",
        "wardrobe": "|".join(es.WARDROBE) + " (인물 미등장 시 null)",
        "expression_restraint": "true|false — 절제된 표정(무표정~차분) 기조 여부",
        "secondary_roles": "조연 서술 (의료인·연구원 등, 없으면 빈 문자열)",
    }
    if industry == "beauty":
        schema["skin_look"] = "|".join(es.SKIN_LOOK)
        schema["hair"] = "|".join(es.HAIR)
    return schema


def _output_schema(industry: str, secondary: str | None = None) -> str:
    profile: dict = {
        "industry_category": industry,
        "product_category_norm": "|".join(es.PRODUCT_CATEGORY_NORM[industry]),
        "product_subtype": "|".join(es.PRODUCT_SUBTYPE[industry]),
        "product_category_raw": "제품·소재 카테고리 한국어 원문 (예: 스킨케어 (세럼))",
        "target_gender": "|".join(es.TARGET_GENDER),
        "usp_category": "|".join(es.USP_CATEGORY) + " — 핵심 차별화 유형 1개",
        "usp_summary": "핵심 USP 1문장 (무엇으로 차별화하는지 구체 서술)",
        "positioning_category": "|".join(es.POSITIONING_CATEGORY) + " — 포지셔닝 전략 1개",
        "price_tier": "|".join(es.PRICE_TIER)
                      + " — 가격대 포지션 (럭셔리 연출·가격/할인 소구 등 근거, 불명확하면 unknown)",
        "summary": "세그먼트 검색용 요약 3~4문장 (제품·타겟·핵심 메시지·톤앤무드)",
    }
    if secondary:
        profile["industry_secondary"] = secondary
    return json.dumps({
        "profile": profile,
        "casting": _casting_schema(industry),
        "elements": [{
            "element_type": "|".join(es.ELEMENT_TYPES),
            "element_subtype": "해당 element_type 의 subtype enum 값 하나",
            "cut_refs": [1],
            "description": "요소가 무엇인지 한국어 1~2문장 (시각 요소·카피 인용 포함)",
            "production_detail": "몇 번째 컷에서 어떤 촬영기법·편집·사운드로 구현했는지 서술",
        }],
    }, ensure_ascii=False, indent=2)


_RULES = (
    "[추출 규칙]\n"
    "  - 시나리오에 실제 기술된 내용에만 근거한다. 창작·추정 금지.\n"
    "  - opening_hook / casting_direction / narrative_pattern 은 각 1개 레코드만 출력한다.\n"
    "  - 인물이 등장하지 않으면 casting_direction 은 subtype 'none', casting 의 인물 필드는 null.\n"
    "  - sensory_demo_shot / trust_device / cta_device / product_shot 는 해당 요소가 전혀 없으면\n"
    "    subtype 'none' 레코드 1개를 출력한다 (관습의 의도적 생략을 집계하기 위함,\n"
    "    예: 무형 서비스 광고는 product_shot 'none').\n"
    "  - color_light_code / copy_device / sound_pattern 은 해당하는 만큼 출력한다.\n"
    "  - 같은 subtype 이 여러 컷에 반복되면 레코드 1개에 cut_refs 로 컷 번호를 모은다.\n"
    "  - enum 에 없는 유형이면 subtype 'other' 를 쓰고 description 에 유형을 구체적으로 서술한다.\n"
    "  - 클리셰인지 아닌지 판정하지 않는다. 요소 사실만 기록한다.\n\n"
)

_FOOTER = "모든 필드를 빠짐없이 채운다. 첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"


def _condense_scenario(scenario: dict) -> str:
    """추출에 필요한 필드를 압축한다. cut_index 는 cut_refs 인용을 위해 유지한다."""
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


def build_element_prompt(scenario: dict, industry: str, secondary: str | None = None) -> str:
    """주/부 산업 팩이 반영된 크리에이티브 요소 추출 프롬프트를 생성한다."""
    industry_desc = f"{industry}+{secondary} 복합 산업" if secondary else f"{industry} 산업"
    return (
        f"너는 광고 크리에이티브 분석 전문가다. 아래 [시나리오]({industry_desc} 광고)에서\n"
        "클리셰 분석용 크리에이티브 요소를 [subtype 사전]의 enum 으로 분류해\n"
        "[출력 스키마] JSON 으로 추출하라.\n\n"
        + _RULES
        + _FOOTER
        + f"[subtype 사전]\n{_enum_guide(industry, secondary)}\n\n"
        + f"[시나리오]\n{_condense_scenario(scenario)}\n\n"
        + f"[출력 스키마 — 값으로 대체하여 채워라]\n{_output_schema(industry, secondary)}"
    )


def compute_duration(scenario: dict) -> float | None:
    """마지막 씬의 time 종료값에서 영상 길이를 계산한다 (예: '13.70~15.00s' → 15.0)."""
    scenes = scenario.get("scenes") or []
    if not scenes:
        return None
    nums = re.findall(r"(\d+(?:\.\d+)?)", str(scenes[-1].get("time", "")))
    return float(nums[-1]) if nums else None


def extract_elements(scenario: dict, industry: str = "other", industry_secondary: str | None = None) -> dict:
    """시나리오에서 요소를 추출하고 industry/duration 을 코드로 보강한다."""
    result = call_claude(build_element_prompt(scenario, industry, industry_secondary), timeout=300)
    if "error" in result:
        return result
    duration = compute_duration(scenario)
    profile = result.setdefault("profile", {})
    profile["industry_category"] = industry
    if industry_secondary:
        profile["industry_secondary"] = industry_secondary
    if duration is not None:
        profile["duration_sec"] = duration
        profile["duration_bucket"] = es.duration_bucket(duration)
    casting = result.get("casting") or {}
    if "expression_restraint" in casting:  # LLM 이 "true"/"false" 문자열로 줄 때 bool 정규화
        casting["expression_restraint"] = str(casting["expression_restraint"]).lower() == "true"
    return result
