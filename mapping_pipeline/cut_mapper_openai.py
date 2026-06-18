"""컷 분석 결과와 시나리오 txt를 OpenAI로 매핑한다."""
from mapping_pipeline.cut_mapper import _PROMPT, _assemble, _format_cuts
from utils.openai_caller import DEFAULT_MODEL, call_openai


def map_cuts_to_scenes_openai(
    cut_analysis: list[dict],
    scenario_txt: str,
    model: str = DEFAULT_MODEL,
) -> list[dict]:
    """컷 분석과 시나리오 원문을 OpenAI로 매핑하고 scene_to_cuts 배열을 반환한다."""
    prompt = _PROMPT.format(
        cut_summary=_format_cuts(cut_analysis),
        scenario_txt=scenario_txt,
    )
    result = call_openai(prompt, model=model)
    return _assemble(
        raw_scenes=result.get("scenes", []),
        raw_mappings=result.get("mappings", []),
        cut_analysis=cut_analysis,
    )
