"""컷 분석 결과와 시나리오 txt를 내용 기반으로 매핑한다."""
from utils.gemini_caller import DEFAULT_MODEL, call_gemini

_PROMPT = """다음은 광고 영상 컷 분석 결과와 시나리오 원문이다.
시나리오 원문에서 Scene을 파악하고, 각 cut이 어느 Scene에 해당하는지
내용(등장인물·사물·행동·분위기)을 기준으로 판단하라.
시간대는 무시하고 내용만 본다.

--- Scene 구분 방법 예시 ---
시나리오 원문은 아래 두 가지 형식 중 하나로 들어온다.
공통 규칙: "숫자~숫자초:" 또는 "숫자–숫자s:" 처럼 시간 범위로 시작하는 세그먼트 하나가 Scene 하나다.
실제 영상 시간과 일치하지 않아도 된다. 시간 표기는 오직 Scene 수를 세는 단서로만 쓴다.

[형식 A — 줄바꿈으로 구분, 한국어 시간 표기]
0~3초: CU+빠른 푸시인, 차가운 쿨톤의 실내에서 구직자의 손과 스마트폰이 여러 채용 공고를 빠르게 넘기다가 멈칫하고, 화면 밖으로 흩어지던 공고 카드들이 정리되지 않은 채 왼쪽에서 오른쪽으로 스쳐 지나가며 마지막에 질문이 크게 남는 느낌의 구성.
3~7초: MS+좌→우 트래킹, 잡코리아 앱 화면이 크게 보이며 직무·지역·경력·급여 조건 필터를 적용하자 조건에 맞는 공고들이 빠르게 정렬되어 한 화면 안으로 모이고, 분산된 공고가 길이 열린 듯 정돈되는 장면.
7~11초: MS+오버숄더 슬라이드, 지원 카드와 진행 현황 보드가 이어진 화면에서 지원 완료, 서류 진행, 확인 필요 상태가 한눈에 보이고, 손가락이 말없이 화면을 탭하며 흐름을 따라가는 장면.
11~15초: WS+고정 롱샷, 밝은 웜톤 배경 위에 잡코리아 브랜드 비주얼, 앱 화면, QR 영역과 짧은 URL 배치가 크게 보이고, 모바일로 스캔하는 동작이 암시되는 마무리 구도.

위 예시에서 Scene은 정확히 4개다:
  Scene 1 → "0~3초" 세그먼트
  Scene 2 → "3~7초" 세그먼트
  Scene 3 → "7~11초" 세그먼트
  Scene 4 → "11~15초" 세그먼트

[형식 B — 줄바꿈 없이 한 문단, 영어 시간 표기]
0–2s: Macro push-in on pizza slice surface, cheese stretching as slice lifts. 2–3.5s: Slow rotation of frosted black can entering frame right, lime green accent reflecting through condensation beads. 3.5–7s: Can tab opens, carbonation bubbles erupt in slow-motion, dark cola liquid crashes into glass. 7–11s: Lime wedge half-submerged rotating in orbital motion, juice particles dispersing left-to-right. 11–13s: Macro static of frosted can beside fresh lime slice, water droplets trickling down. 13–15s: Wide static shot of 355ml 24-can bundle pack centered on clean white seamless background.

위 예시에서 Scene은 정확히 6개다 (줄바꿈이 없어도 시간 표기 기준으로 분리):
  Scene 1 → "0–2s" 세그먼트
  Scene 2 → "2–3.5s" 세그먼트
  Scene 3 → "3.5–7s" 세그먼트
  Scene 4 → "7–11s" 세그먼트
  Scene 5 → "11–13s" 세그먼트
  Scene 6 → "13–15s" 세그먼트
--- 예시 끝 ---

[중요] scenes 배열의 Scene 수는 시나리오 원문의 Scene 수와 반드시 일치해야 한다.
Scene이 많아지거나 줄어들어서는 안 된다.
해당 Scene과 매칭되는 cut을 찾지 못한 경우에도 scenes 배열에 Scene을 포함시키고,
mappings에서 그 Scene에 대한 항목을 생략하면 된다.

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
        valid = [ci for ci in indices if ci in time_map]
        start_s = min(time_map[ci][0] for ci in valid) if valid else None
        end_s = max(time_map[ci][1] for ci in valid) if valid else None
        result.append({
            "scene": sc,
            "label": s.get("label", ""),
            "cut_indices": indices,
            "start_s": start_s,
            "end_s": end_s,
        })
    return result
