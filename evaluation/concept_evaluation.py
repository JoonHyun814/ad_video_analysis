"""scenario_analysis.json 기반으로 광고 컨셉을 추출하고 설득력을 채점한다 (claude 백엔드)."""
import json

from utils.llm_caller import call_claude

_INDUSTRY = "beauty|food_beverage|retail_ecommerce|finance|healthcare|fashion|tech_electronics|automotive|entertainment|travel|education|gaming|other"
_APPEAL_TYPE = "humor|maternal_love|vanity|fear|sex_appeal|comparison|rational_info|emotional_storytelling|testimonial|scarcity_urgency|nostalgia|aspiration|other"

_SCORE_CRITERIA: dict[str, str] = {
    "interest": "시나리오가 오프닝 훅·비주얼 임팩트·의외성 등으로 소비자의 흥미와 호기심을 얼마나 강하게 유발하는가",
    "consistency": "concept·strategy·narrative·씬 전개·key_messages가 서로 모순 없이 하나의 톤으로 일관되게 유지되는가",
    "relevance": "strategy(설득 전략)와 표현이 target_persona 및 제품 특성(usp·positioning)과 얼마나 밀접하게 연관되는가",
    "recurrence": "핵심 메시지·비주얼·슬로건 요소가 씬 전반에 걸쳐 반복·강조되어 기억에 남을 가능성을 높이는가",
}

_SCORE_RUBRIC = (
    "[채점 기준 — score는 1~5 정수 중 하나를 선택]\n"
    "  5 : 기준을 매우 뛰어나게 충족 — 시나리오 전반에서 명확하고 설득력 있게 구현됨\n"
    "  4 : 기준을 충족하나 일부 씬에서 임팩트가 약하거나 표현이 다소 평이함\n"
    "  3 : 기준이 부분적으로 드러나나 두드러지지 않고 평균적인 수준에 머무름\n"
    "  2 : 기준 관련 요소가 미약하게 존재하나 의도적 설계로 보기 어려움\n"
    "  1 : 기준에 해당하는 요소가 거의 드러나지 않거나 완전히 누락됨\n\n"
)

_PROMPT_FOOTER = (
    "각 scores 항목 출력: score(1~5 정수), reasoning(한국어·2문장 이내).\n"
    "첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
)


def _build_schema() -> str:
    """추출 필드와 1~5점 채점 필드를 하나의 출력 스키마로 구성한다."""
    scores = {
        key: {"criterion": criterion, "score": "<1~5 정수>", "reasoning": "한국어로 간결하게"}
        for key, criterion in _SCORE_CRITERIA.items()
    }
    return json.dumps({
        "industry_category": _INDUSTRY,
        "product_category": "제품 카테고리 명칭 (한국어, 예: 스킨케어, 음료, 쇼핑몰, 금융서비스)",
        "target_persona": "타겟 소비자 설명 (연령대·성별·라이프스타일·관심사·구매 동기 포함, 2~3문장)",
        "usp": "경쟁 제품 대비 차별화 포인트 한 문장",
        "positioning": "브랜드/제품 포지셔닝 (1문장)",
        "strategy": {
            "appeal_type": _APPEAL_TYPE,
            "description": "광고가 소비자를 설득하거나 인상적으로 느끼게 하는 구체적 전략 설명 (예: 유머러스, 모성애, 과시욕 등), 1~2문장",
        },
        "scores": scores,
    }, ensure_ascii=False, indent=2)


def _condense_scenario(scenario: dict) -> str:
    """평가에 필요한 필드를 압축해 반환한다."""
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
                    b["description"][:80] for b in s.get("beats", [])[:2] if b.get("description")
                ),
            }
            for s in scenario.get("scenes", [])
        ],
    }
    return json.dumps(condensed, ensure_ascii=False, indent=2)


def build_concept_eval_prompt(scenario: dict) -> str:
    """컨셉 추출 + 설득력 채점 프롬프트를 생성한다."""
    scenario_text = _condense_scenario(scenario)
    schema = _build_schema()
    return (
        "너는 광고 마케팅 전략 평가 전문가다. 아래 [시나리오]를 분석해 [출력 스키마]의 추출 필드를 채우고,\n"
        "scores의 각 criterion을 심사하라.\n\n"
        + _SCORE_RUBRIC
        + _PROMPT_FOOTER
        + f"[시나리오]\n{scenario_text}\n\n"
        + f"[출력 스키마 — 추출 필드는 값으로 대체, scores의 criterion은 고정, score·reasoning만 채워라]\n{schema}"
    )


def _compute_overall(raw: dict) -> dict:
    """scores 4개 항목의 평균을 overall_score 로 추가한다."""
    if "error" in raw:
        return raw
    scores = raw.get("scores", {})
    values = [float(v.get("score", 0)) for v in scores.values() if "score" in v]
    raw["overall_score"] = round(sum(values) / len(values), 2) if values else 0.0
    return raw


def evaluate_concept(scenario: dict) -> dict:
    """시나리오에서 광고 컨셉을 추출하고 설득력을 채점한다 (claude 백엔드)."""
    prompt = build_concept_eval_prompt(scenario)
    raw = call_claude(prompt, timeout=300)
    return _compute_overall(raw)
