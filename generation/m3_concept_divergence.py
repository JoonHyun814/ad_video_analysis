"""M3 컨셉 발산 — 서로 명확히 다른 광고 컨셉 5~8개 생성 (평가·순위 금지)."""
import json

from utils.llm_dispatch import call_llm

_SCHEMA = (
    '{"concepts": ['
    '  {"id": "C1",'
    '   "title": "컨셉 제목",'
    '   "hook": "첫 3초 후크 — 시청자를 붙잡는 방식",'
    '   "tone": "톤앤매너 (예: 유머·감성·정보·도발·권위)",'
    '   "core_tension": "광고가 해소하는 핵심 긴장 또는 욕망",'
    '   "visual_language": "주요 시각 언어·미장센 한 줄",'
    '   "narrative_structure": "서사 구조 (예: PAS·스토리·비교·증언·일상)",'
    '   "distinctiveness_note": "다른 컨셉과 명확히 다른 이유"}'
    ' ]}'
)


def _format_reference_ads(reference_ads: list[dict]) -> str:
    """ChromaDB query() 결과를 프롬프트에 끼울 텍스트 블록으로 직렬화."""
    lines: list[str] = []
    for i, ad in enumerate(reference_ads, 1):
        meta = ad.get("metadata") or {}
        doc = (ad.get("document") or "").strip()
        lines.append(
            f"[참고 광고 {i}] video_id={meta.get('video_id')}, "
            f"brand={meta.get('brand_name', '-')}, "
            f"산업={meta.get('industry_category', '-')}/제품={meta.get('product_category', '-')}"
        )
        if doc:
            lines.append(doc)
        lines.append("")
    return "\n".join(lines)


def build_prompt(brief: dict, m1: dict, m2: dict, reference_ads: list[dict] | None = None) -> str:
    """브리프+M1+M2(+선택적 참고 광고)에서 M3 컨셉 발산 프롬프트를 만든다."""
    brief_text = json.dumps(brief, ensure_ascii=False, indent=2)
    m1_text = json.dumps(m1, ensure_ascii=False, indent=2)
    m2_text = json.dumps(m2, ensure_ascii=False, indent=2)
    ref_section = ""
    if reference_ads:
        ref_section = (
            "\n[참고: 포지셔닝이 유사한 기존 광고]\n"
            "주의 — 모방하지 말고 '명확히 다른 컨셉'을 발산하기 위한 비교 기준으로만 활용해라.\n"
            "각 컨셉의 distinctiveness_note 에 어떤 점에서 이 참고 광고들과 다른지 명시해라.\n\n"
            f"{_format_reference_ads(reference_ads)}\n"
        )
    return (
        "너는 광고 크리에이티브 디렉터다.\n"
        "아래 브리프·인사이트·포지셔닝을 바탕으로 광고 컨셉을 5~8개 발산해라.\n\n"
        "규칙 (반드시 준수):\n"
        "1. '좋은 컨셉 1개'가 아니라 '서로 명확히 다른 컨셉 5~8개'를 만드는 것이 목표다.\n"
        "2. 각 컨셉은 tone·hook·narrative_structure 중 최소 2가지가 달라야 한다.\n"
        "3. 앵커링 방지 — 첫 번째 컨셉에 수렴하지 말고 각 컨셉을 독립적으로 전개해라.\n"
        "4. 이 단계에서 평가·순위·추천은 절대 하지 않는다. 발산만 한다.\n"
        "5. M2의 dual_mandate(전환+기억)와 M1의 CEP/Job을 각 컨셉에 다른 방식으로 반영해라.\n\n"
        "첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
        f"[브리프]\n{brief_text}\n\n"
        f"[M1 소비자 인사이트]\n{m1_text}\n\n"
        f"[M2 포지셔닝]\n{m2_text}\n"
        f"{ref_section}\n"
        f"[출력 스키마]\n{_SCHEMA}"
    )


def run(
    brief: dict,
    m1: dict,
    m2: dict,
    *,
    reference_ads: list[dict] | None = None,
    backend: str = "claude",
    gemini_model: str = "",
    codex_model: str | None = None,
) -> dict:
    """컨셉 발산(M3)을 수행한다. reference_ads 가 있으면 참고 컨텍스트로 주입한다."""
    return call_llm(
        build_prompt(brief, m1, m2, reference_ads),
        backend=backend, gemini_model=gemini_model, codex_model=codex_model,
    )
