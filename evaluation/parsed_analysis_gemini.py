"""scenario_analysis 결과를 DB 저장용 parsed 구조로 정제한다 (gemini 백엔드)."""
from pipeline.cuts import Cut
from evaluation.parsed_analysis import _inject_meta, build_prompt
from utils.gemini_caller import DEFAULT_MODEL, call_gemini


def analyze_parsed_gemini(
    scenario: dict,
    cuts: list[Cut],
    cut_analysis: list[dict],
    scene_analysis: list[dict],
    stt_segments: list[dict],
    audio_data: dict | None,
    model: str = DEFAULT_MODEL,
) -> dict:
    """Gemini로 parsed 구조를 생성한다."""
    prompt = build_prompt(scenario, cuts, cut_analysis, scene_analysis, stt_segments, audio_data)
    result = call_gemini(prompt, model=model, timeout=600)
    _inject_meta(result, cuts, model)
    return result
