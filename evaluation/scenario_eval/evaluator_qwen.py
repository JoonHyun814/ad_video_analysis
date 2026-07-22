"""qwen 백엔드 시나리오 평가."""
from pipeline import qwen_client
from evaluation.scenario_eval.evaluator import _compute_scores, build_eval_prompt, build_eval_prompt_no_brief


def evaluate_scenario_qwen(brief: dict, scenario: dict) -> dict:
    """Qwen 로컬 모델로 시나리오를 평가한다."""
    prompt = build_eval_prompt(brief, scenario)
    raw_text = qwen_client.infer([], prompt, max_new_tokens=4096)
    raw = qwen_client.parse_json(raw_text)
    return _compute_scores(raw)


def evaluate_scenario_no_brief_qwen(scenario: dict) -> dict:
    """브리프 없이 시나리오만으로 평가한다 (qwen 백엔드). brief_fidelity 항목 제외."""
    prompt = build_eval_prompt_no_brief(scenario)
    raw_text = qwen_client.infer([], prompt, max_new_tokens=4096)
    raw = qwen_client.parse_json(raw_text)
    return _compute_scores(raw)
