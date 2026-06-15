"""M1 소비자 인사이트 — Job / Forces / CEP 트리거 / 검증 가정 추출."""
import json

from utils.llm_dispatch import call_llm

_SCHEMA = (
    '{"core_jobs": [{"job": "핵심 Job 한 줄 (고객 언어)", "verbatim": "실제 고객 표현 예시"}],'
    ' "forces": {'
    '   "push": ["현재 대안에서 밀어내는 요인"],'
    '   "pull": ["우리 카테고리로 당기는 요인"],'
    '   "anxiety": ["전환 불안 요인"],'
    '   "habit": ["기존 습관 저항 요인"]'
    ' },'
    ' "triggers": [{"trigger": "구체 상황·계기", "cep": "CEP 후보 태그"}],'
    ' "critical_assumptions": ['
    '   {"assumption": "검증 가정 한 줄", "risk": "틀렸을 때 영향", "how_to_test": "검증 방법"}'
    ' ]}'
)


def build_prompt(brief: dict) -> str:
    """브리프에서 M1 소비자 인사이트 프롬프트를 만든다."""
    brief_text = json.dumps(brief, ensure_ascii=False, indent=2)
    return (
        "너는 소비자 심리·Jobs-to-be-Done 전문가다.\n"
        "아래 광고 브리프를 바탕으로 소비자 인사이트를 분석한다.\n"
        "추측이 아니라 실제 리뷰·VoC를 마이닝하는 관점으로, "
        "'왜 이 사람이 대안에서 우리 카테고리로 갈아타는가'를 "
        "고객의 정확한 표현(verbatim)으로 재구성해라.\n\n"
        "분석 항목:\n"
        "1. core_jobs: 고객이 이 제품으로 해결하려는 핵심 Job (3개 이상, 고객 언어로 서술)\n"
        "2. forces: 스위칭 포스 4요소 — push(현재 대안 불만) / pull(신제품 기대) / "
        "anxiety(전환 걱정) / habit(기존 습관 고수)\n"
        "3. triggers: 구매 계기가 되는 구체 상황·CEP(Category Entry Point) 후보 (3개 이상)\n"
        "4. critical_assumptions: '이 인사이트가 틀리면 캠페인 전체가 무너지는' 가정 Top 3\n\n"
        "첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
        f"[브리프]\n{brief_text}\n\n"
        f"[출력 스키마]\n{_SCHEMA}"
    )


def run(
    brief: dict,
    *,
    backend: str = "claude",
    gemini_model: str = "",
    codex_model: str | None = None,
) -> dict:
    """브리프에서 소비자 인사이트(M1)를 추출한다."""
    return call_llm(build_prompt(brief), backend=backend, gemini_model=gemini_model, codex_model=codex_model)
