"""scenario_analysis 에서 광고 브리프를 추출한다 (claude 기본 백엔드)."""
import json
import re
import subprocess
import time

from evaluation.schemas import _BRIEF_SCHEMA

_RETRY_DELAYS = (30, 60, 120)


def build_brief_prompt(scenario: dict) -> str:
    """브리프 추출용 프롬프트를 생성한다."""
    condensed = _condense_scenario(scenario)
    return (
        "너는 광고 기획 전문가다. 아래 광고 시나리오를 분석해 광고 브리프를 추출하라.\n"
        "추론이 불가능한 필드는 빈 문자열 또는 빈 배열로 둔다.\n"
        "첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
        f"[시나리오]\n{condensed}\n\n"
        f"[출력 스키마]\n{_BRIEF_SCHEMA}"
    )


def generate_brief(scenario: dict) -> dict:
    """시나리오에서 브리프를 추출한다 (claude 백엔드)."""
    return _call_claude(build_brief_prompt(scenario))


def _condense_scenario(scenario: dict) -> str:
    """평가에 필요한 핵심 필드만 추출해 문자열로 반환한다."""
    out: dict = {k: scenario[k] for k in ("brand", "concept", "narrative", "key_messages", "cast") if k in scenario}
    scenes_summary = []
    for s in scenario.get("scenes", []):
        beats = [{"type": b["type"], "desc": b["description"][:150]} for b in s.get("beats", [])]
        scenes_summary.append({"cut": s["cut_index"], "time": s.get("time", ""), "beats": beats})
    out["scenes"] = scenes_summary
    return json.dumps(out, ensure_ascii=False, indent=2)


def _call_claude(prompt: str) -> dict:
    cmd = ["claude", "-p", prompt]
    result = subprocess.CompletedProcess(args=cmd, returncode=1, stdout="")
    for attempt, delay in enumerate((*_RETRY_DELAYS, None), start=1):
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if "529" not in result.stdout and "Overloaded" not in result.stdout:
            return _parse_json(result.stdout)
        if delay is None:
            break
        print(f"      API 과부하(529), {delay}초 후 재시도 ({attempt}/{len(_RETRY_DELAYS)})...")
        time.sleep(delay)
    return _parse_json(result.stdout)


def _parse_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start != -1:
        try:
            return json.loads(text[start:])
        except json.JSONDecodeError:
            pass
    return {"error": "parse_failed", "raw": text[:500]}
