"""qwen 백엔드 브리프 추출."""
from pipeline import qwen_client
from evaluation.brief.brief_generator import build_brief_prompt


def generate_brief_qwen(scenario: dict) -> dict:
    """Qwen 로컬 모델로 브리프를 추출한다."""
    prompt = build_brief_prompt(scenario)
    raw = qwen_client.infer([], prompt, max_new_tokens=2048)
    return qwen_client.parse_json(raw)
