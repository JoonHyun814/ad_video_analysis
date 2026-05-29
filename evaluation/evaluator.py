"""brief_analysis 와 scenario_analysis 를 비교해 Phase 1 평가 결과를 생성한다 (claude 기본 백엔드)."""
import json
from utils.json_utils import parse_json as _parse_json
import subprocess
import time

from evaluation.schemas import build_eval_schema

_RETRY_DELAYS = (30, 60, 120)


def build_eval_prompt(brief: dict, scenario: dict) -> str:
    """평가 프롬프트를 생성한다."""
    brief_text = json.dumps(brief, ensure_ascii=False, indent=2)
    scenario_text = _condense_scenario(scenario)
    schema = build_eval_schema()
    return (
        "너는 광고 품질 평가 전문가다. [브리프]와 [시나리오]를 참고해 [평가 스키마]의 각 criterion을 심사하라.\n"
        "각 항목: result('pass'/'partial'/'fail'), score(1.0/0.5/0.0), reasoning(한국어·간결하게).\n"
        "첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
        f"[브리프]\n{brief_text}\n\n"
        f"[시나리오]\n{scenario_text}\n\n"
        f"[평가 스키마 — criterion은 고정, result/score/reasoning만 채워라]\n{schema}"
    )


def evaluate_scenario(brief: dict, scenario: dict) -> dict:
    """시나리오를 브리프와 비교 평가한다 (claude 백엔드)."""
    prompt = build_eval_prompt(brief, scenario)
    raw = _call_claude(prompt)
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
        avg = sum(i.get("score", 0.0) for i in items) / len(items)
        cat_data["score"] = round(avg, 3)
        cat_scores.append(avg)
    raw["overall_score"] = round(sum(cat_scores) / len(cat_scores), 3) if cat_scores else 0.0
    raw["phase"] = "phase1_text"
    return raw


def _call_claude(prompt: str) -> dict:
    cmd = ["claude", "-p", prompt]
    result = subprocess.CompletedProcess(args=cmd, returncode=1, stdout="")
    for attempt, delay in enumerate((*_RETRY_DELAYS, None), start=1):
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if "529" not in result.stdout and "Overloaded" not in result.stdout:
            return _parse_json(result.stdout)
        if delay is None:
            break
        print(f"      API 과부하(529), {delay}초 후 재시도 ({attempt}/{len(_RETRY_DELAYS)})...")
        time.sleep(delay)
    return _parse_json(result.stdout)

