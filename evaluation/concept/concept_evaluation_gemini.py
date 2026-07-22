"""scenario_analysis.json 기반 광고 컨셉 추출 (gemini 백엔드)."""
from evaluation.concept.concept_evaluation import build_concept_eval_prompt
from utils.gemini_caller import DEFAULT_MODEL, call_gemini


def evaluate_concept_gemini(scenario: dict, model: str = DEFAULT_MODEL) -> dict:
    """Gemini로 광고 컨셉을 추출한다."""
    prompt = build_concept_eval_prompt(scenario)
    return call_gemini(prompt, model=model, timeout=300)
