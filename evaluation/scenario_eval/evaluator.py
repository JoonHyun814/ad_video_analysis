"""brief_analysis 와 scenario_analysis 를 비교해 Phase 1 평가 결과를 생성한다 (claude 기본 백엔드)."""
import json
from utils.json_utils import parse_json as _parse_json
from utils.llm_caller import call_claude

from evaluation.schemas import build_eval_schema, build_eval_schema_no_brief, build_eval_schema_video, build_eval_schema_platform

# ── 채점 루브릭 + 퓨샷 예시 (두 프롬프트 공통) ────────────────────────────────
_SCORING_GUIDE = (
    "[채점 기준 — score는 아래 5단계 정의 중 정확히 하나를 선택]\n"
    "  1.0  : 기준을 완벽히 충족 — 해당 요소가 씬 묘사에 명확하고 일관되게 구현됨\n"
    "  0.75 : 기준을 충족하나 일부 씬에서 논리적 비약 또는 불완전한 표현이 있음\n"
    "  0.5  : 기준이 언급되었으나 서사적 인과성 또는 묘사의 구체성이 부족함\n"
    "  0.25 : 기준 관련 요소가 산발적으로 존재하나 의도적 설계로 보기 어려움\n"
    "  0    : 기준에 해당하는 요소가 완전히 누락됨\n\n"
    "[채점 예시 — 아래 두 예시를 앵커로 삼아 일관된 점수를 부여하라]\n"
    "  HIGH(1.0) opening_hook_elements: 클로즈업 전환과 정적→충격음 대비가 동시에 사용되어\n"
    "    즉각적 시선 집중을 유발하고 다음 씬에 대한 호기심을 명확히 유도함 → score: 1.0\n"
    "  LOW(0.25) narrative_rising_action: 씬이 순차적으로 나열되나 갈등 요소 없이 편안한\n"
    "    분위기만 유지되어 브랜드 개입의 당위적 공간이 형성되지 않음 → score: 0.25\n\n"
)

_PROMPT_FOOTER = (
    "각 항목 출력: score(위 5단계 숫자 중 하나), reasoning(한국어·2문장 이내).\n"
    "첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
)


def build_eval_prompt(brief: dict, scenario: dict) -> str:
    """평가 프롬프트를 생성한다."""
    brief_text = json.dumps(brief, ensure_ascii=False, indent=2)
    scenario_text = _condense_scenario(scenario)
    schema = build_eval_schema()
    return (
        "너는 광고 품질 평가 전문가다. [브리프]와 [시나리오]를 참고해 [평가 스키마]의 각 criterion을 심사하라.\n\n"
        + _SCORING_GUIDE
        + _PROMPT_FOOTER
        + f"[브리프]\n{brief_text}\n\n"
        + f"[시나리오]\n{scenario_text}\n\n"
        + f"[평가 스키마 — key·criterion은 고정, score·reasoning만 채워라]\n{schema}"
    )


def evaluate_scenario(brief: dict, scenario: dict) -> dict:
    """시나리오를 브리프와 비교 평가한다 (claude 백엔드)."""
    prompt = build_eval_prompt(brief, scenario)
    raw = call_claude(prompt, timeout=600)
    return _compute_scores(raw)


def build_eval_prompt_no_brief(scenario: dict) -> str:
    """브리프 없이 시나리오만으로 평가하는 프롬프트를 생성한다."""
    scenario_text = _condense_scenario(scenario)
    schema = build_eval_schema_no_brief()
    return (
        "너는 광고 품질 평가 전문가다. [시나리오]를 참고해 [평가 스키마]의 각 criterion을 심사하라.\n\n"
        + _SCORING_GUIDE
        + _PROMPT_FOOTER
        + f"[시나리오]\n{scenario_text}\n\n"
        + f"[평가 스키마 — key·criterion은 고정, score·reasoning만 채워라]\n{schema}"
    )


def evaluate_scenario_no_brief(scenario: dict) -> dict:
    """브리프 없이 시나리오만으로 평가한다 (claude 백엔드). brief_fidelity 항목 제외."""
    prompt = build_eval_prompt_no_brief(scenario)
    raw = call_claude(prompt, timeout=600)
    return _compute_scores(raw)


def _condense_scenario(scenario: dict) -> str:
    """평가에 필요한 필드를 압축해 반환한다."""
    out: dict = {k: scenario[k] for k in ("brand", "concept", "narrative", "key_messages", "cast") if k in scenario}
    scenes_summary = []
    for s in scenario.get("scenes", []):
        beats = [{"type": b["type"], "desc": b["description"][:200]} for b in s.get("beats", [])]
        scenes_summary.append({"cut": s["cut_index"], "time": s.get("time", ""), "beats": beats})
    out["scenes"] = scenes_summary
    return json.dumps(out, ensure_ascii=False, indent=2)


def _compute_scores(raw: dict) -> dict:
    """카테고리별·전체 평균 점수를 계산해 추가한다."""
    if "error" in raw:
        return raw
    categories = raw.get("categories", {})
    cat_scores: list[float] = []
    for cat_data in categories.values():
        items = cat_data.get("items", [])
        if not items:
            cat_data["score"] = 0.0
            continue
        avg = sum(float(i.get("score", 0.0)) for i in items) / len(items)
        cat_data["score"] = round(avg, 3)
        cat_scores.append(avg)
    raw["overall_score"] = round(sum(cat_scores) / len(cat_scores), 3) if cat_scores else 0.0
    raw["phase"] = "phase1_text"
    return raw



