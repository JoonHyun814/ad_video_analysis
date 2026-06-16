"""scenario_analysis.json 에서 카테고리 메타데이터를 추출한다 (gemini 백엔드)."""
from evaluation.category_analysis import build_category_prompt, parse_duration
from utils.gemini_caller import DEFAULT_MODEL, call_gemini


def analyze_category_gemini(scenario: dict, brief: dict | None = None, model: str = DEFAULT_MODEL) -> dict:
    """시나리오에서 카테고리 메타데이터를 추출한다 (gemini 백엔드)."""
    result = call_gemini(build_category_prompt(scenario, brief), model=model, timeout=300)
    if "error" not in result:
        result["duration"] = parse_duration(scenario)
        result["brand_name"] = scenario.get("brand", "")
    return result
