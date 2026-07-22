"""scenario_analysis 에서 광고 브리프를 추출한다 (gemini 백엔드)."""
from evaluation.brief.brief_generator import build_brief_prompt
from utils.gemini_caller import DEFAULT_MODEL, call_gemini


def generate_brief_gemini(scenario: dict, model: str = DEFAULT_MODEL) -> dict:
    """Gemini로 브리프를 추출한다."""
    return call_gemini(build_brief_prompt(scenario), model=model)
