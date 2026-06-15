"""M6 레드팀 프리모템 — 미래 시점에서 캠페인 실패를 역산해 Critical 킬스위치를 작동."""
import json

from utils.llm_dispatch import call_llm

_SCHEMA = (
    '{"verdict": "proceed | kill | return_to_m5 | return_to_gate_a | return_to_phase1",'
    ' "failure_modes": ['
    '   {'
    '     "severity": "Critical | Major | Minor",'
    '     "scenario": "이 캠페인이 왜 실패했는가 — 과거형으로 서술",'
    '     "root_module": "M1 | M2 | M3 | M4 | M5 | 외부요인",'
    '     "mitigation": "이 실패를 막으려면 해당 모듈에서 무엇을 바꿔야 하는가"'
    '   }'
    ' ],'
    ' "unresolved_criticals": ["킬스위치를 발동시키는 Critical 실패 시나리오"],'
    ' "verdict_rationale": "최종 판정 이유"}'
)

_SEVERITY_GUIDE = (
    "- Critical: 캠페인 자체를 멈춰야 할 수준 (법적 리스크·브랜드 훼손·핵심 전략 결함)\n"
    "- Major: 성과를 절반 이하로 떨어뜨리는 수준 (메시지 혼선·타겟 불일치·채널 미스매치)\n"
    "- Minor: 수정하면 해결되는 수준 (카피 약점·UX 마찰·타이밍 이슈)"
)

_VERDICT_GUIDE = (
    "- proceed: Critical이 없고 Major도 수정 범위 내\n"
    "- kill: Critical 중 미해결 항목이 1개 이상 — 즉시 진행 차단\n"
    "- return_to_m5: 스크립트 레벨 수정으로 해결 가능\n"
    "- return_to_gate_a: 컨셉 자체를 바꿔야 해결 가능\n"
    "- return_to_phase1: 인사이트·포지셔닝부터 다시 해야 해결 가능"
)


def build_prompt(brief: dict, m5: dict) -> str:
    """브리프+M5 스크립트에서 M6 레드팀 프롬프트를 만든다."""
    brief_text = json.dumps(brief, ensure_ascii=False, indent=2)
    m5_text = json.dumps(m5, ensure_ascii=False, indent=2)
    return (
        "너는 제작팀과 완전히 분리된 반증 담당 레드팀이다.\n"
        "시점을 미래로 옮겨라. 이 캠페인은 이미 실패했다. 왜 실패했는가?\n\n"
        "작업 방식:\n"
        "1. 실패를 과거형으로 서술한다 ('이 광고는 ~했기 때문에 실패했다').\n"
        "2. 각 실패 모드의 심각도를 분류한다:\n"
        f"{_SEVERITY_GUIDE}\n"
        "3. 각 실패를 책임 모듈로 환원한다 ('이건 M__에서 고쳐야 했다').\n"
        "4. 판정:\n"
        f"{_VERDICT_GUIDE}\n"
        "5. Critical이 하나라도 있으면 unresolved_criticals에 리스트업하고 "
        "verdict를 'kill' 또는 반송으로 설정한다.\n\n"
        "첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
        f"[브리프]\n{brief_text}\n\n"
        f"[M5 DR 스크립트]\n{m5_text}\n\n"
        f"[출력 스키마]\n{_SCHEMA}"
    )


def run(
    brief: dict,
    m5: dict,
    *,
    backend: str = "claude",
    gemini_model: str = "",
    codex_model: str | None = None,
) -> dict:
    """레드팀 프리모템(M6)을 수행한다."""
    return call_llm(build_prompt(brief, m5), backend=backend, gemini_model=gemini_model, codex_model=codex_model)
