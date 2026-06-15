"""M4 컨셉 비평·킬 — 독립 비평가 역할로 약한 컨셉을 제거하고 최강 1~2개를 선정."""
import json

from utils.llm_dispatch import call_llm

_SCHEMA = (
    '{"verdict": "proceed | return_to_phase1",'
    ' "selected": ["C1"],'
    ' "selected_rationale": "선정 이유 — 전략 부합도·차별성·실행 가능성 기준으로",'
    ' "killed": ['
    '   {"id": "C2", "reason": "탈락 이유 — 구체적으로, 감추지 않고"}'
    ' ],'
    ' "return_reason": "return_to_phase1일 때만 — 어떤 인사이트가 부족해서 반송하는지"}'
)

_KILL_CRITERIA = (
    "- 전략 부합도: M1 Job·CEP와 연결되는가, M2 dual_mandate를 달성하는가\n"
    "- 차별성: 기존 경쟁 광고와 얼마나 다른가\n"
    "- 후크 강도: 첫 3초에 이탈을 막을 수 있는가\n"
    "- 실행 가능성: 예산·법규·브랜드 가이드 범위 안에 있는가\n"
    "- 기억 가능성: 한 번 보고 브랜드를 기억할 수 있는가"
)


def build_prompt(m3: dict) -> str:
    """M3 컨셉 목록에서 M4 킬 프롬프트를 만든다."""
    m3_text = json.dumps(m3, ensure_ascii=False, indent=2)
    return (
        "너는 독립 광고 비평가다. 인센티브가 반대다 — 컨셉을 살리는 게 아니라 "
        "약한 걸 정직하게 죽이고 가장 강한 1~2개만 남기는 것이 일이다.\n\n"
        "역할 규칙:\n"
        "1. 아래 평가 기준으로 각 컨셉을 독립적으로 평가한다.\n"
        f"{_KILL_CRITERIA}\n"
        "2. 최강 1~2개를 selected에 담는다. 동점이면 1개만 선정한다.\n"
        "3. 나머지는 killed에 넣고 이유를 구체적으로 적는다. '약하다'는 이유로는 부족하다.\n"
        "4. 선정된 컨셉도 모두 전략적으로 약하다면 verdict를 'return_to_phase1'으로 설정하고 "
        "return_reason에 어떤 인사이트가 부족한지 적는다. "
        "킬은 실패가 아니라 게이트가 작동한 신호다.\n\n"
        "첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
        f"[M3 컨셉 목록]\n{m3_text}\n\n"
        f"[출력 스키마]\n{_SCHEMA}"
    )


def run(
    m3: dict,
    *,
    backend: str = "claude",
    gemini_model: str = "",
    codex_model: str | None = None,
) -> dict:
    """컨셉 비평·킬(M4)을 수행하고 선정 결과를 반환한다."""
    return call_llm(build_prompt(m3), backend=backend, gemini_model=gemini_model, codex_model=codex_model)
