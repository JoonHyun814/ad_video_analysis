"""scenario_analysis.json 기반 광고 컨셉 추출 (codex 백엔드)."""
from evaluation.concept.concept_evaluation import build_concept_eval_prompt
from utils.llm_caller import call_codex


def evaluate_concept_codex(scenario: dict, model: str | None = None) -> dict:
    """codex CLI로 광고 컨셉을 추출한다."""
    prompt = build_concept_eval_prompt(scenario)
    return call_codex(prompt, model=model, timeout=300)
