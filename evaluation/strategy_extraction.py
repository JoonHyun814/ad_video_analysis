"""scenario_analysis.json 에서 M1(인사이트)·M2(포지셔닝)·M3(컨셉) 스키마를 역추출한다."""
import json

from utils.llm_dispatch import call_llm

from evaluation.strategy_schemas import (
    M1_GUIDE,
    M1_SCHEMA,
    M2_GUIDE,
    M2_SCHEMA,
    M3_GUIDE,
    M3_SCHEMA,
)

_COMMON_HEADER = (
    "너는 DR-CTV(직접 반응형 커넥티드 TV) 영상 광고 전략 분석 전문가다.\n"
    "아래 [시나리오]는 이미 완성된 광고 영상을 분석한 결과다. 이 광고가 기획될 당시\n"
    "산출됐을 전략 문서를 역추론하여 [출력 스키마]를 채워라.\n\n"
    "[공통 규칙]\n"
    "- 시나리오에서 관찰되는 장면·대사·자막·연출에 근거를 접지하라.\n"
    "- 관찰로 확인 불가한 추정(시장 규모·경쟁사·수치 등)에는 [가설] 태그와 신뢰도(상/중/하)를 달아라.\n"
    "- 스키마의 키 이름을 그대로 사용하고, 스키마에 없는 키를 새로 만들지 않는다.\n"
    "- 모든 최상위 키를 빠짐없이 포함한다(값이 없으면 빈 배열/빈 문자열).\n"
    "- 첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
)


def _condense_scenario(scenario: dict) -> str:
    """전략 역추출에 필요한 시나리오 필드를 압축해 반환한다 (beat 전량 유지, 설명만 축약)."""
    condensed: dict = {
        "brand": scenario.get("brand", ""),
        "title": scenario.get("title", ""),
        "concept": scenario.get("concept", ""),
        "narrative": scenario.get("narrative", ""),
        "key_messages": scenario.get("key_messages", []),
        "production_notes": scenario.get("production_notes", ""),
        "cast": [c.get("description", "")[:120] for c in scenario.get("cast", [])[:4]],
        "scenes": [
            {
                "cut_index": s["cut_index"],
                "time": s.get("time", ""),
                "beats": [
                    {"type": b.get("type", ""), "desc": b["description"][:200]}
                    for b in s.get("beats", [])
                    if b.get("description")
                ],
            }
            for s in scenario.get("scenes", [])
        ],
    }
    return json.dumps(condensed, ensure_ascii=False, indent=2)


def build_m1_prompt(scenario: dict) -> str:
    """시나리오에서 M1 소비자 인사이트를 역추출하는 프롬프트를 만든다."""
    return (
        _COMMON_HEADER
        + M1_GUIDE
        + "\n"
        + f"[시나리오]\n{_condense_scenario(scenario)}\n\n"
        + f"[출력 스키마 — 값으로 대체하여 채워라]\n{M1_SCHEMA}"
    )


def build_m2_prompt(scenario: dict, m1: dict) -> str:
    """시나리오와 M1 결과에서 M2 포지셔닝을 역추출하는 프롬프트를 만든다."""
    m1_text = json.dumps(m1, ensure_ascii=False, indent=2)
    return (
        _COMMON_HEADER
        + M2_GUIDE
        + "\n- M1 이 확정한 시장 정의문(marketdefinition)을 경계로 받아 그 안에서 포지셔닝하라.\n\n"
        + f"[시나리오]\n{_condense_scenario(scenario)}\n\n"
        + f"[M1 핸드오프]\n{m1_text}\n\n"
        + f"[출력 스키마 — 값으로 대체하여 채워라]\n{M2_SCHEMA}"
    )


def build_m3_prompt(scenario: dict, m1: dict, m2: dict) -> str:
    """시나리오와 M1·M2 결과에서 M3 컨셉 발산을 역추출하는 프롬프트를 만든다."""
    context = {
        "corejob": m1.get("corejob", ""),
        "humantruth": m1.get("humantruth", {}),
        "culturalcodes": m1.get("culturalcodes", []),
        "verbatim": m1.get("verbatim", []),
        "m2": m2,
    }
    context_text = json.dumps(context, ensure_ascii=False, indent=2)
    return (
        _COMMON_HEADER
        + M3_GUIDE
        + "\n"
        + f"[시나리오]\n{_condense_scenario(scenario)}\n\n"
        + f"[전략 맥락 — M1·M2 핸드오프]\n{context_text}\n\n"
        + f"[출력 스키마 — 값으로 대체하여 채워라]\n{M3_SCHEMA}"
    )


def extract_strategy(
    scenario: dict,
    *,
    backend: str = "claude",
    gemini_model: str = "",
    codex_model: str | None = None,
    timeout: int = 600,
) -> dict:
    """M1→M2→M3 순차 역추출 후 {"m1", "m2", "m3"} 하나의 dict 로 반환한다."""
    kwargs = {"backend": backend, "gemini_model": gemini_model, "codex_model": codex_model, "timeout": timeout}

    m1 = call_llm(build_m1_prompt(scenario), **kwargs)
    if "error" in m1:
        return {"m1": m1, "m2": {"error": "skipped: m1 failed"}, "m3": {"error": "skipped: m1 failed"}}

    m2 = call_llm(build_m2_prompt(scenario, m1), **kwargs)
    if "error" in m2:
        return {"m1": m1, "m2": m2, "m3": {"error": "skipped: m2 failed"}}

    m3 = call_llm(build_m3_prompt(scenario, m1, m2), **kwargs)
    return {"m1": m1, "m2": m2, "m3": m3}
