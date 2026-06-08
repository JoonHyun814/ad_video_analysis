"""컷 분석 결과와 시나리오 txt를 내용 기반으로 매핑한다."""
from utils.gemini_caller import DEFAULT_MODEL, call_gemini

_PROMPT = """다음은 광고 영상 컷 분석 결과와 시나리오 원문이다.
시나리오 원문에서 Scene을 파악하고, 각 cut이 어느 Scene에 해당하는지
내용(등장인물·사물·행동·분위기)을 기준으로 판단하라.
시간대는 무시하고 내용만 본다.

[컷 분석]
{cut_summary}

[시나리오 원문]
{scenario_txt}

마크다운 없이 순수 JSON만 출력하라.
{{
  "scenes": [
    {{"scene": <int>, "label": "<Scene 레이블>"}},
    ...
  ],
  "mappings": [
    {{"cut_index": <int>, "scene": <int>, "reason": "<한 문장>"}},
    ...
  ]
}}"""


def map_cuts_to_scenes(
    cut_analysis: list[dict],
    scenario_txt: str,
    model: str = DEFAULT_MODEL,
) -> list[dict]:
    """컷 분석과 시나리오 원문을 LLM으로 매핑하고 scene_to_cuts 배열을 반환한다."""
    prompt = _PROMPT.format(
        cut_summary=_format_cuts(cut_analysis),
        scenario_txt=scenario_txt,
    )
    result = call_gemini(prompt, model=model)
    return _assemble(
        raw_scenes=result.get("scenes", []),
        raw_mappings=result.get("mappings", []),
        cut_analysis=cut_analysis,
    )


def _format_cuts(cut_analysis: list[dict]) -> str:
    lines = []
    for c in cut_analysis:
        idx = c.get("cut_index")
        t = f"{c.get('start_sec', 0):.2f}~{c.get('end_sec', 0):.2f}s"
        lines.append(f"cut {idx} ({t}):")
        for key in ("flow", "subjects", "cast", "camera", "text_flow", "mood_shift"):
            val = c.get(key)
            if val and val != "없음":
                lines.append(f"  {key}: {val}")
    return "\n".join(lines)


def _assemble(
    raw_scenes: list[dict],
    raw_mappings: list[dict],
    cut_analysis: list[dict],
) -> list[dict]:
    time_map = {c["cut_index"]: (c["start_sec"], c["end_sec"]) for c in cut_analysis}

    assignment: dict[int, int] = {}
    for m in raw_mappings:
        ci, sc = m.get("cut_index"), m.get("scene")
        if ci is not None and sc is not None:
            assignment[ci] = sc

    scene_cuts: dict[int, list[int]] = {}
    for ci, sc in assignment.items():
        scene_cuts.setdefault(sc, []).append(ci)

    result = []
    for s in raw_scenes:
        sc = s["scene"]
        indices = sorted(scene_cuts.get(sc, []))
        if not indices:
            continue
        start_s = min(time_map[ci][0] for ci in indices if ci in time_map)
        end_s = max(time_map[ci][1] for ci in indices if ci in time_map)
        result.append({
            "scene": sc,
            "label": s.get("label", ""),
            "cut_indices": indices,
            "start_s": start_s,
            "end_s": end_s,
        })
    return result
