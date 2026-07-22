"""brief_analysis 와 scenario_analysis 를 비교해 평가 결과를 생성한다 (gemini 백엔드)."""
from evaluation.scenario_eval.evaluator import _compute_scores, build_eval_prompt, build_eval_prompt_no_brief
from utils.gemini_caller import DEFAULT_MODEL, call_gemini


def evaluate_scenario_gemini(brief: dict, scenario: dict, model: str = DEFAULT_MODEL) -> dict:
    """Gemini로 시나리오를 브리프와 비교 평가한다."""
    prompt = build_eval_prompt(brief, scenario)
    raw = call_gemini(prompt, model=model, timeout=600)
    return _compute_scores(raw)


def evaluate_scenario_no_brief_gemini(scenario: dict, model: str = DEFAULT_MODEL) -> dict:
    """브리프 없이 시나리오만으로 평가한다 (gemini 백엔드). brief_fidelity 항목 제외."""
    prompt = build_eval_prompt_no_brief(scenario)
    raw = call_gemini(prompt, model=model, timeout=600)
    return _compute_scores(raw)
