"""scenario_analysis.json 기반 광고 컨셉 추출 + 설득력 채점 (qwen 백엔드)."""
from evaluation.concept_evaluation import _compute_overall, build_concept_eval_prompt
from pipeline import qwen_client


def evaluate_concept_qwen(scenario: dict) -> dict:
    """Qwen 로컬 모델로 광고 컨셉을 추출하고 설득력을 채점한다."""
    prompt = build_concept_eval_prompt(scenario)
    raw_text = qwen_client.infer([], prompt, max_new_tokens=4096)
    raw = qwen_client.parse_json(raw_text)
    return _compute_overall(raw)
