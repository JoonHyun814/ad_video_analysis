"""브리프 기반 광고 시나리오 생성 (gemini 백엔드)."""
from generation.scenario_generator import build_scenario_prompt
from utils.gemini_caller import DEFAULT_MODEL, call_gemini


def generate_scenario_gemini(brief: dict, model: str = DEFAULT_MODEL) -> dict:
    """Gemini로 시나리오를 생성한다."""
    return call_gemini(build_scenario_prompt(brief), model=model, timeout=600)
