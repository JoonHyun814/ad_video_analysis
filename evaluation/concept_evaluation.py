"""scenario_analysis.json 기반으로 광고 컨셉을 추출한다 (claude 백엔드)."""
import json

from utils.llm_caller import call_claude

_INDUSTRY = "beauty|food_beverage|retail_ecommerce|finance|healthcare|fashion|tech_electronics|automotive|entertainment|travel|education|gaming|other"
_APPEAL_TYPE = "humor|parody_wordplay|maternal_love|vanity|fear|sex_appeal|comparison|rational_info|emotional_storytelling|testimonial|scarcity_urgency|nostalgia|aspiration|other"
_PERCEIVED_VALUE = "functional_quality|functional_price|emotional|social|other"
_MESSAGE_STRATEGY = "informational|transformational|other"
_EXECUTION_STYLE = "slice_of_life|scientific_evidence|fantasy|fashion|other"
_PERSONA_SEGMENTATION = "demographic|psychographic|behavioral|other"
_USP_TYPE = "functional_tangible|emotional_intangible|economic_price|other"
_POSITIONING_STRATEGY = "by_product_innovation|by_service_quality|by_cost_leadership|by_target_needs|other"

_CATEGORY_GUIDE = (
    "[category 필드 참고 — 애매하면 'other' 선택]\n"
    "  target_persona.category    : demographic(연령·성별·소득 등 인구통계) / psychographic(라이프스타일·가치관·성격) / "
    "behavioral(구매행동·사용빈도·충성도) 중 타겟을 나누는 주된 기준\n"
    "  usp.category               : functional_tangible(가시적 기능·성능 차별화) / emotional_intangible(감성·무형 차별화) / "
    "economic_price(가격·경제성 차별화) 중 USP 유형\n"
    "  positioning.category       : by_product_innovation(제품 혁신) / by_service_quality(서비스 품질) / "
    "by_cost_leadership(비용 우위) / by_target_needs(타겟 니즈 충족) 중 포지셔닝 근거\n"
    "  appeal_type.category       : humor·parody_wordplay·maternal_love·vanity·fear·sex_appeal·comparison·"
    "rational_info·emotional_storytelling·testimonial·scarcity_urgency·nostalgia·aspiration·other 중 소구 유형\n"
    "  perceived_value.category   : functional_quality(품질·성능) / functional_price(가성비·비용) / "
    "emotional(감성·즐거움) / social(과시·사회적 이미지) 중 광고가 가장 강조하는 소비자 지각 가치\n"
    "  message_strategy.category  : informational(스펙·논리적 정보 전달) / transformational(경험·감정 변화 강조) "
    "중 광고의 메시지 전달 방식\n"
    "  execution_style.category   : slice_of_life(일상 문제-해결) / scientific_evidence(데이터·전문가 근거) / "
    "fantasy(비현실적 과장) / fashion(스타일·미학 중심) 중 연출 방식\n\n"
)

_FORMAT_NOTE = (
    "[출력 형식 규칙]\n"
    "  industry_category 는 배열이며, pipe(|) 구분 enum 중 실제 해당하는 값만 1~2개 담는다 "
    "(복합적이면 2개까지, 명확하면 1개). enum 문자열 전체를 그대로 출력하지 않는다.\n"
    "  product_category 는 한국어 값 하나만 출력한다 (설명·근거 없이).\n\n"
    "  target_persona·usp·positioning·appeal_type·perceived_value·message_strategy·execution_style "
    "7개 필드는 모두\n"
    '  {"category": [...], "description": "...", "production_detail": "..."} 형태로 출력한다.\n'
    "  - category   : 위 [category 필드 참고]의 enum 중 1~2개 배열 (appeal_type 은 복합적이면 2개까지)\n"
    "  - description: 해당 요소가 무엇인지 한국어 줄글로 2~3문장 설명 (시각적 요소·카피 인용 포함)\n"
    "  - production_detail: 이 요소를 표현하기 위해 실제로 어떤 연출을 썼는지 구체적으로 서술 — "
    '예) "짧은 인생을 좋은 것으로 채우자는 usp를 반영하기 위해 3번째 컷에서 클로즈업으로 미소를 강조했다"'
    "처럼 몇 번째 컷(cut_index)에서 어떤 촬영기법·편집·사운드를 사용했는지 명시한다.\n\n"
)

_APPEAL_DESC_HINT = (
    "  appeal_type.description 참고: text_overlay·dialogue에 원곡 가사를 바꾼 개사, 유명 콘텐츠 패러디, "
    "언어유희(말장난) 같은 텍스트 기반 장치가 보이면 무엇을 어떻게 바꿨는지 구체적으로 명시하라.\n\n"
)

_PROMPT_FOOTER = (
    "모든 필드를 빠짐없이 채운다. 첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
)


def _detail_field(enum: str) -> dict:
    """category(배열, enum 중 1~2개)·description(줄글 설명)·production_detail(연출 세부 설명) 템플릿을 만든다."""
    return {
        "category": [enum],
        "description": "한국어 줄글 설명 (2~3문장)",
        "production_detail": "몇 번째 컷에서 어떤 촬영기법·연출로 구현했는지 구체적으로 서술",
    }


def _build_schema() -> str:
    """추출 필드로 구성된 출력 스키마를 만든다."""
    return json.dumps({
        "industry_category": [_INDUSTRY],
        "product_category": "제품 카테고리 명칭 (한국어, 예: 스킨케어, 음료, 쇼핑몰, 금융서비스)",
        "target_persona": _detail_field(_PERSONA_SEGMENTATION),
        "usp": _detail_field(_USP_TYPE),
        "positioning": _detail_field(_POSITIONING_STRATEGY),
        "appeal_type": _detail_field(_APPEAL_TYPE),
        "perceived_value": _detail_field(_PERCEIVED_VALUE),
        "message_strategy": _detail_field(_MESSAGE_STRATEGY),
        "execution_style": _detail_field(_EXECUTION_STYLE),
    }, ensure_ascii=False, indent=2)


def _condense_scenario(scenario: dict) -> str:
    """평가에 필요한 필드를 압축해 반환한다.

    beat를 앞 2개로 자르면 text_overlay·dialogue가 대부분 뒤쪽 순서라 통째로 누락되어,
    개사·패러디·언어유희처럼 자막/대사에만 드러나는 설득 장치를 모델이 볼 수 없게 된다.
    그래서 beat 개수를 자르지 않고 전부 포함하되, 각 설명만 200자로 축약한다.
    cut_index 를 유지하는 이유는 production_detail 에서 "몇 번째 컷"을 구체적으로 인용하기 위해서다.
    """
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
                "beats": [
                    {"type": b.get("type", ""), "desc": b["description"][:200]}
                    for b in s.get("beats", [])
                    if b.get("description")
                ],
            }
            for s in scenario.get("scenes", [])
        ],
    }
    return json.dumps(condensed, ensure_ascii=False, indent=2)


def build_concept_eval_prompt(scenario: dict) -> str:
    """컨셉 추출 프롬프트를 생성한다."""
    scenario_text = _condense_scenario(scenario)
    schema = _build_schema()
    return (
        "너는 광고 마케팅 전략 평가 전문가다. 아래 [시나리오]를 분석해 [출력 스키마]의 필드를 채워라.\n\n"
        + _FORMAT_NOTE
        + _CATEGORY_GUIDE
        + _APPEAL_DESC_HINT
        + _PROMPT_FOOTER
        + f"[시나리오]\n{scenario_text}\n\n"
        + f"[출력 스키마 — 값으로 대체하여 채워라]\n{schema}"
    )


def evaluate_concept(scenario: dict) -> dict:
    """시나리오에서 광고 컨셉을 추출한다 (claude 백엔드)."""
    prompt = build_concept_eval_prompt(scenario)
    return call_claude(prompt, timeout=300)
