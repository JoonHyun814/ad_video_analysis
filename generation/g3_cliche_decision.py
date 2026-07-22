"""G3 — 클리셰 리포트를 보고 패턴별 따를지(follow)/피할지(avoid)/비틀지(subvert)를 결정한다.

카테고리 코드(점유율이 매우 높은 관행)는 제품 이해를 돕는 장치라 따르는 게 안전한 경우가 많고,
크리에이티브 클리셰(과밀 소구·연출)는 차별화 기회다 — 이 구분을 LLM 판단의 축으로 강제한다.
"""
import json

from generation.cliche_report import report_for_prompt
from utils.llm_dispatch import call_llm

_SCHEMA = (
    '{"decisions": ['
    '  {"pattern": "리포트의 pattern 키 그대로 (예: appeal_type=emotional_storytelling)",'
    '   "kind": "category_code|creative_cliche|dense_cluster",'
    '   "share": 0.55,'
    '   "decision": "follow|avoid|subvert",'
    '   "reason": "결정 근거 1~2문장 (브랜드 지위·세그먼트 분포 인용)"}'
    ' ],'
    ' "whitespace_picks": ['
    '  {"pattern": "리포트 whitespace 중 채택한 패턴", "rationale": "이 공백이 기회인 이유"}'
    ' ],'
    ' "creative_direction": "위 결정들을 종합한 크리에이티브 방향 요약 (3~4문장)"}'
)


def build_prompt(g1: dict, report: dict) -> str:
    """G1 정규화 결과 + 클리셰 리포트에서 G3 결정 프롬프트를 만든다."""
    slim = report_for_prompt(report)
    return (
        "너는 광고 크리에이티브 전략가다. 아래는 이 광고가 진입할 세그먼트"
        "(장르×산업×타겟×USP)의 기존 광고 분포 리포트다. 패턴별로 따를지/피할지/비틀지를 결정해라.\n\n"
        "판단 기준:\n"
        "1. category_codes (점유율 매우 높음): 이 카테고리 광고로 읽히게 하는 관행일 가능성이 크다. "
        "제품 이해와 직결되면 follow, 브랜드가 파괴적 지위를 노리면 subvert 를 고려한다.\n"
        "2. creative_cliches (과밀 소구·연출): 차별화 기회다. 기본적으로 avoid/subvert 를 검토하되, "
        "brand_position 이 challenger/new_entrant 인데 인지도 확보가 우선이면 follow 도 가능하다.\n"
        "3. clusters 중 is_dense=true: 세그먼트의 실제 클리셰 덩어리다. dominant_patterns 를 근거로 결정한다.\n"
        "4. whitespace: 세그먼트에서 아직 쓰이지 않은 패턴이다. 브랜드 전략에 맞는 것만 골라라 "
        "(모든 공백이 기회는 아니다 — 안 쓰인 이유가 있는 패턴도 있다).\n"
        f"5. 표본 신뢰도: n={report.get('n')}, relax_level={report.get('relax_level')}. "
        "n 이 작거나 완화 수준이 global 에 가까우면 결정 강도를 낮추고 reason 에 명시해라.\n\n"
        f"[브랜드/타겟 전략 (G1)]\n{json.dumps(g1, ensure_ascii=False, indent=2)}\n\n"
        f"[클리셰 리포트 (G2)]\n{json.dumps(slim, ensure_ascii=False, indent=2)}\n\n"
        "decisions 에는 category_codes·creative_cliches 전체와 is_dense=true 클러스터를 모두 포함해라. "
        "dense_cluster 항목의 pattern 은 해당 클러스터 dominant_patterns 의 첫 값을 쓴다.\n"
        "첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
        f"[출력 스키마]\n{_SCHEMA}"
    )


def run(
    g1: dict,
    report: dict,
    *,
    backend: str = "claude",
    gemini_model: str = "",
    codex_model: str | None = None,
) -> dict:
    """클리셰 리포트 기반 follow/avoid/subvert 결정(G3)을 반환한다."""
    return call_llm(build_prompt(g1, report),
                    backend=backend, gemini_model=gemini_model, codex_model=codex_model)
