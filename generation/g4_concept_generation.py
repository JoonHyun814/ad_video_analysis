"""G4 — G3 클리셰 결정을 준수하는 서로 다른 광고 컨셉 5개를 생성한다.

각 컨셉은 creative_summary(임베딩 검증용 서술)와 applied_decisions(어떤 결정을 어떻게 반영했는지)를
반드시 포함한다 — G5 가 이 서술을 임베딩해 클리셰 클러스터와의 거리를 실측 검증한다.
"""
import json

from evaluation.concept.concept_vector_store import APPEAL_TYPE_CHOICES, EXECUTION_STYLE_CHOICES
from utils.llm_dispatch import call_llm

_SCHEMA = (
    '{"concepts": ['
    '  {"id": "C1",'
    '   "title": "컨셉 제목",'
    '   "hook": "첫 3초 후크 — 시청자를 붙잡는 방식",'
    f'   "appeal_type": "{"|".join(APPEAL_TYPE_CHOICES)}|other",'
    f'   "execution_style": "{"|".join(EXECUTION_STYLE_CHOICES)}|other",'
    '   "core_tension": "광고가 해소하는 핵심 긴장 또는 욕망",'
    '   "visual_language": "주요 시각 언어·미장센 한 줄",'
    '   "narrative_structure": "서사 구조 (예: PAS·스토리·비교·증언·일상)",'
    '   "creative_summary": "이 컨셉의 소구·연출·서사를 3~4문장으로 서술 (기존 광고 분석 문서와 같은 문체)",'
    '   "applied_decisions": ['
    '     {"pattern": "G3 decisions 의 pattern 키", "decision": "follow|avoid|subvert",'
    '      "how": "이 컨셉이 그 결정을 구체적으로 어떻게 반영했는지 한 문장"}'
    '   ]}'
    ' ]}'
)


def build_prompt(brief: dict, g1: dict, g3: dict) -> str:
    """브리프 + G1 전략 + G3 클리셰 결정에서 컨셉 생성 프롬프트를 만든다."""
    return (
        "너는 광고 크리에이티브 디렉터다. 아래 브리프·타겟 전략·클리셰 결정을 바탕으로 "
        "광고 컨셉을 정확히 5개 생성해라.\n\n"
        "규칙 (반드시 준수):\n"
        "1. G3 의 모든 decision 을 각 컨셉이 준수해야 한다 — avoid 패턴은 쓰지 않고, "
        "follow 패턴은 반영하고, subvert 패턴은 기대를 뒤집는 방식으로 변형한다.\n"
        "2. whitespace_picks 는 5개 중 최소 2개 컨셉이 실제로 활용해라.\n"
        "3. '좋은 컨셉 1개'가 아니라 '서로 명확히 다른 컨셉 5개'가 목표다 — "
        "appeal_type·hook·narrative_structure 중 최소 2가지가 컨셉 간에 달라야 한다.\n"
        "4. creative_summary 는 G5 임베딩 검증에 쓰인다 — 소구 유형·연출 스타일·서사를 "
        "구체적 장면 언어로 서술해라 (추상적 슬로건 금지).\n"
        "5. 이 단계에서 평가·순위·추천은 하지 않는다.\n\n"
        f"[브리프]\n{json.dumps(brief, ensure_ascii=False, indent=2)}\n\n"
        f"[타겟 전략 (G1)]\n{json.dumps(g1, ensure_ascii=False, indent=2)}\n\n"
        f"[클리셰 결정 (G3)]\n{json.dumps(g3, ensure_ascii=False, indent=2)}\n\n"
        "첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
        f"[출력 스키마]\n{_SCHEMA}"
    )


def run(
    brief: dict,
    g1: dict,
    g3: dict,
    *,
    backend: str = "claude",
    gemini_model: str = "",
    codex_model: str | None = None,
) -> dict:
    """클리셰 결정을 준수하는 컨셉 5개(G4)를 생성한다."""
    return call_llm(build_prompt(brief, g1, g3),
                    backend=backend, gemini_model=gemini_model, codex_model=codex_model)
