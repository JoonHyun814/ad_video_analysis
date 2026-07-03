"""scenario_analysis.json 기반 광고 컨셉 추출 + 설득력 채점 (gemini 백엔드)."""
from evaluation.concept_evaluation import _compute_overall, build_concept_eval_prompt
from utils.gemini_caller import DEFAULT_MODEL, call_gemini


def evaluate_concept_gemini(scenario: dict, model: str = DEFAULT_MODEL) -> dict:
    """Gemini로 광고 컨셉을 추출하고 설득력을 채점한다."""
    prompt = build_concept_eval_prompt(scenario)
    raw = call_gemini(prompt, model=model, timeout=300)
    return _compute_overall(raw)
