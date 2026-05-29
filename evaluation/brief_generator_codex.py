"""codex 백엔드 브리프 추출."""
from evaluation.brief_generator import build_brief_prompt
from utils.llm_caller import call_codex


def generate_brief_codex(scenario: dict, model: str | None = None) -> dict:
    """codex exec 로 브리프를 추출한다."""
    return call_codex(build_brief_prompt(scenario), model=model)
