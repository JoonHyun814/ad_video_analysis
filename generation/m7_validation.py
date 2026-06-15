"""M7 저비용 검증 — 합성 사전스크린(Stage1) + 인간 게이트 시뮬레이션(Stage2)."""
import json

from utils.llm_dispatch import call_llm

_SCHEMA = (
    '{"stage1_synthetic": {'
    '  "variants_tested": ['
    '    {"variant_id": "V1", "description": "변형 내용 한 줄", "relative_rank": 1,'
    '     "weak_points": ["약점 목록"], "survivor": true}'
    '  ],'
    '  "filter_rationale": "1차 필터 기준과 탈락 이유 요약"'
    ' },'
    ' "stage2_human_gate": {'
    '  "go_criteria": {'
    '    "hook_rate_threshold": "목표 후크율 (%)",'
    '    "brand_recall_threshold": "브랜드 회상 목표 (%)",'
    '    "purchase_intent_lift": "구매 의향 증가 목표"'
    '  },'
    '  "simulated_results": {'
    '    "hook_rate_estimate": "합성 오디언스 기반 후크율 추정",'
    '    "brand_recall_estimate": "브랜드 회상 추정",'
    '    "purchase_intent_estimate": "구매 의향 추정"'
    '  },'
    '  "result": "Go | No-Go",'
    '  "redirect": "None | M5 | GATE_A | PHASE1",'
    '  "redirect_reason": "No-Go일 때 — 어느 부분을 수정해야 하는가"'
    ' }}'
)

_STAGE1_NOTE = (
    "Stage 1 — 합성 오디언스 필터:\n"
    "- 주요 타겟 페르소나 3~5개를 합성해 각 변형(variant)을 시청했을 때의 반응을 시뮬레이션한다.\n"
    "- 상대 순위만 신뢰한다. 절대 수치는 참고용.\n"
    "- 하위 50% 변형을 1차 탈락시킨다. 비용 0으로 약한 변형을 거른다.\n"
)

_STAGE2_NOTE = (
    "Stage 2 — 인간 게이트 시뮬레이션:\n"
    "- go_criteria를 먼저 선언한다 (사후 합리화 방지).\n"
    "- 생존한 변형에 대해 합성 오디언스 기반 수치를 추정한다.\n"
    "- 추정치가 go_criteria를 충족하면 Go, 아니면 No-Go + redirect.\n"
    "- 실제 인간 테스트는 이 시뮬레이션 결과를 통과한 변형에만 진행하도록 설계되어 있다.\n"
)


def _build_variants(m5: dict, m6: dict) -> list[dict]:
    """M5 스크립트와 M6 피드백에서 테스트 변형 목록을 생성한다."""
    script_title = m5.get("l3_script", {}).get("title", "원본 스크립트")
    base_variant = {"variant_id": "V1", "description": f"{script_title} (원본)", "is_base": True}
    variants = [base_variant]
    for i, mode in enumerate(m6.get("failure_modes", [])[:3], start=2):
        if mode.get("severity") in ("Major", "Minor") and mode.get("mitigation"):
            variants.append({
                "variant_id": f"V{i}",
                "description": f"M6 수정안: {mode['mitigation'][:60]}",
                "is_base": False,
            })
    return variants


def build_prompt(m5: dict, m6: dict, brief: dict) -> str:
    """M5+M6에서 M7 검증 프롬프트를 만든다."""
    variants = _build_variants(m5, m6)
    brief_text = json.dumps({"brand": brief.get("brand"), "product": brief.get("product"),
                              "target_persona": brief.get("target_persona"), "usp": brief.get("usp")},
                             ensure_ascii=False, indent=2)
    variants_text = json.dumps(variants, ensure_ascii=False, indent=2)
    m5_summary = json.dumps({
        "concept": m5.get("l3_script", {}).get("concept", ""),
        "hook": m5.get("l1_container", {}).get("A_attention", ""),
        "engine": m5.get("l2_engine", {}).get("type", ""),
        "key_messages": m5.get("l3_script", {}).get("key_messages", []),
    }, ensure_ascii=False, indent=2)
    return (
        "너는 광고 사전 테스트 전문가다.\n"
        "아래 광고 변형들을 2단계로 검증한다.\n\n"
        f"{_STAGE1_NOTE}\n"
        f"{_STAGE2_NOTE}\n"
        "go_criteria는 브리프·M5 스크립트를 바탕으로 현실적인 목표치를 먼저 설정한 후 평가한다.\n\n"
        "첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
        f"[브리프 요약]\n{brief_text}\n\n"
        f"[M5 스크립트 요약]\n{m5_summary}\n\n"
        f"[테스트 변형 목록]\n{variants_text}\n\n"
        f"[출력 스키마]\n{_SCHEMA}"
    )


def run(
    m5: dict,
    m6: dict,
    brief: dict,
    *,
    backend: str = "claude",
    gemini_model: str = "",
    codex_model: str | None = None,
) -> dict:
    """합성 사전스크린 + 인간 게이트 시뮬레이션(M7)을 수행한다."""
    return call_llm(build_prompt(m5, m6, brief), backend=backend, gemini_model=gemini_model, codex_model=codex_model)
