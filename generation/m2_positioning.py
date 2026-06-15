"""M2 포지셔닝 — Dunford 차별화(인마켓 5%) × Ehrenberg-Bass 가용성(비인마켓 95%) 설계."""
import json

from utils.llm_dispatch import call_llm

_SCHEMA = (
    '{"inmarket_5pct": {'
    '  "dunford_differentiation": "Dunford 포지셔닝 한 문장",'
    '  "key_claims": ["차별화 클레임 (경쟁 대비 우위 근거 포함)"],'
    '  "decision_triggers": ["이 5%가 최종 선택하게 만드는 결정적 요인"]'
    ' },'
    ' "non_inmarket_95pct": {'
    '  "cep_moments": ["기억에 심을 CEP 상황 — 브랜드와 연결할 계기 순간들"],'
    '  "dba_assets": ["Distinctive Brand Asset 후보 — 색·소리·캐릭터·슬로건"],'
    '  "ehrenberg_bass_note": "이 95%의 기억에 어떻게 침투할지 한 단락"'
    ' },'
    ' "dual_mandate": "광고 한 편이 전환(5%)과 기억 심기(95%)를 동시에 달성하는 설계 방향",'
    ' "cep_dba_matrix": [{"cep": "상황", "dba": "연결할 브랜드 자산"}]}'
)


def build_prompt(brief: dict, m1: dict) -> str:
    """브리프+M1 인사이트에서 M2 포지셔닝 프롬프트를 만든다."""
    brief_text = json.dumps(brief, ensure_ascii=False, indent=2)
    m1_text = json.dumps(m1, ensure_ascii=False, indent=2)
    return (
        "너는 브랜드 전략·포지셔닝 전문가다 (Dunford + Ehrenberg-Bass 프레임워크 전문).\n"
        "아래 브리프와 M1 소비자 인사이트를 바탕으로 이중 포지셔닝 전략을 수립해라.\n\n"
        "전략의 두 축:\n"
        "1. 인마켓 5% (지금 구매 고려 중인 소비자) → Dunford 차별화 전략\n"
        "   '왜 경쟁 대안이 아닌 우리가 더 나은가'를 증거 기반으로 설계한다.\n"
        "2. 비인마켓 95% (지금 구매 고려 안 하는 소비자) → Ehrenberg-Bass 정신적 가용성\n"
        "   CEP(Category Entry Point)와 DBA(Distinctive Brand Asset)를 연결해 "
        "기억 구조(memory structure)를 심는다.\n"
        "3. dual_mandate: 광고 한 편이 전환(5%)과 기억 침투(95%)를 동시에 달성하도록 방향을 설정한다.\n\n"
        "첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
        f"[브리프]\n{brief_text}\n\n"
        f"[M1 소비자 인사이트]\n{m1_text}\n\n"
        f"[출력 스키마]\n{_SCHEMA}"
    )


def run(
    brief: dict,
    m1: dict,
    *,
    backend: str = "claude",
    gemini_model: str = "",
    codex_model: str | None = None,
) -> dict:
    """브리프+M1로 포지셔닝 전략(M2)을 수립한다."""
    return call_llm(build_prompt(brief, m1), backend=backend, gemini_model=gemini_model, codex_model=codex_model)
