"""브리프 기반 광고 시나리오 생성 (qwen 백엔드)."""
from pipeline import qwen_client
from generation.scenario_generator import build_scenario_prompt


def generate_scenario_qwen(brief: dict) -> dict:
    """Qwen 로컬 모델로 시나리오를 생성한다."""
    prompt = build_scenario_prompt(brief)
    raw = qwen_client.infer([], prompt, max_new_tokens=4096)
    return qwen_client.parse_json(raw)
