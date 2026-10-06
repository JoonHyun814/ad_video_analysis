"""scenario_analysis.json 에서 마케팅 카테고리 메타데이터를 추출한다 (claude 백엔드)."""
import json
import re

from utils.llm_caller import call_claude

_INDUSTRY = "beauty|food_beverage|retail_ecommerce|finance|healthcare|fashion|tech_electronics|automotive|entertainment|travel|education|gaming|other"
_OBJECTIVE = "awareness|consideration|conversion"
_PLACEMENT = "ctv_15s|ctv_30s|youtube_pre_roll_15s|youtube_pre_roll_30s|sns_15s|sns_30s|other"
_CREATIVE = "brand_film|performance_dr|lifestyle|testimonial|product_demo|ugc_style|animation|hybrid|other"
_NARRATIVE = "hook_body_close|problem_solution|before_after|storytelling|feature_list|emotional_journey|other"
_ROLES = "HOOK|ESTABLISH_CONTEXT|PROBLEM|EMOTIONAL_APPEAL|FEATURE|DEMO|TESTIMONIAL|SOCIAL_PROOF|CTA|BRAND_CLOSE"

_SCHEMA = json.dumps({
    "industry_category": _INDUSTRY,
    "product_category": "제품 카테고리 명칭 (한국어, 예: 스킨케어, 음료, 쇼핑몰, 금융서비스)",
    "campaign_objective": _OBJECTIVE,
    "placement": _PLACEMENT,
    "target_age_min": "<정수, 예: 20>",
    "target_age_max": "<정수, 예: 39>",
    "target_persona": "타겟 소비자 설명 (연령대·성별·라이프스타일·관심사·구매 동기 포함, 2~3문장)",
    "key_message": "광고의 핵심 전달 메시지 한 문장",
    "usp": "경쟁 제품 대비 차별화 포인트 한 문장",
    "positioning": "브랜드/제품 포지셔닝 (1문장)",
    "hook_strategy": "첫 3초 시청자 주목 전략 (1~2문장)",
    "creative_style": _CREATIVE,
    "narrative_structure": _NARRATIVE,
    "role_sequence": f"씬 순서별 역할을 쉼표로 나열 (선택지: {_ROLES})",
    "key_scenes": "핵심 씬 3~5개 설명 (각 씬의 화면 구성·전달 메시지, 한 씬 당 1~2문장)",
}, ensure_ascii=False, indent=2)


def parse_duration(scenario: dict) -> float:
    """마지막 씬 time 필드에서 광고 길이(초)를 파싱한다."""
    scenes = scenario.get("scenes", [])
    if not scenes:
        return 0.0
    last_time = scenes[-1].get("time", "")
    m = re.search(r"~(\d+\.?\d*)s", last_time)
    return float(m.group(1)) if m else 0.0


def _condense_scenario(scenario: dict) -> str:
    condensed: dict = {
        "brand": scenario.get("brand", ""),
        "concept": scenario.get("concept", ""),
        "narrative": scenario.get("narrative", ""),
        "key_messages": scenario.get("key_messages", []),
        "production_notes": scenario.get("production_notes", ""),
        "cast_sample": [c.get("description", "")[:120] for c in scenario.get("cast", [])[:3]],
        "scenes": [
            {
                "cut_index": s["cut_index"],
                "time": s.get("time", ""),
                "summary": " | ".join(
                    b["description"][:80]
                    for b in s.get("beats", [])[:2]
                    if b.get("description")
                ),
            }
            for s in scenario.get("scenes", [])
        ],
    }
    return json.dumps(condensed, ensure_ascii=False, indent=2)


def build_category_prompt(scenario: dict, brief: dict | None = None) -> str:
    """카테고리 분석 프롬프트를 생성한다."""
    scenario_text = _condense_scenario(scenario)
    brief_block = ""
    if brief:
        brief_sub = {k: brief[k] for k in ("product", "usp", "target_age", "target_persona", "positioning", "slogan") if k in brief}
        brief_block = f"\n\n[브리프]\n{json.dumps(brief_sub, ensure_ascii=False, indent=2)}"
    duration = parse_duration(scenario)
    return (
        "너는 광고 마케팅 분석 전문가다. 아래 광고 시나리오를 분석하여 마케팅 메타데이터를 JSON으로 추출하라.\n"
        "첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
        f"광고 길이: {duration:.1f}초\n\n"
        f"[시나리오]\n{scenario_text}{brief_block}\n\n"
        f"[출력 스키마]\n{_SCHEMA}"
    )


def analyze_category(scenario: dict, brief: dict | None = None) -> dict:
    """시나리오에서 카테고리 메타데이터를 추출한다 (claude 백엔드)."""
    result = call_claude(build_category_prompt(scenario, brief), timeout=300)
    if "error" not in result:
        result["duration"] = parse_duration(scenario)
        result["brand_name"] = scenario.get("brand", "")
    return result
