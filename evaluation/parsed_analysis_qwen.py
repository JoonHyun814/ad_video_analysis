"""scenario_analysis 결과를 DB 저장용 parsed 구조로 정제한다 (qwen 백엔드)."""
from pipeline import qwen_client
from pipeline.cuts import Cut
from evaluation.parsed_analysis import _inject_meta, build_prompt

_QWEN_MODEL = "unsloth/Qwen2.5-VL-7B-Instruct"


def analyze_parsed_qwen(
    scenario: dict,
    cuts: list[Cut],
    cut_analysis: list[dict],
    scene_analysis: list[dict],
    stt_segments: list[dict],
    audio_data: dict | None,
) -> dict:
    """qwen_client.infer 로 parsed 구조를 생성한다."""
    prompt = build_prompt(scenario, cuts, cut_analysis, scene_analysis, stt_segments, audio_data)
    raw = qwen_client.infer([], prompt, max_new_tokens=4096)
    result = qwen_client.parse_json(raw)
    _inject_meta(result, cuts, _QWEN_MODEL)
    return result
