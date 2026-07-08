"""새 컨셉 파이프라인 CM4 — CM1~CM3 결과로 서로 다른 광고 컨셉 5개를 생성한다 (평가·선정은 CM5, 미구현)."""
import json

from utils.llm_dispatch import call_llm

_APPEAL_TYPE = "humor|parody_wordplay|maternal_love|vanity|fear|sex_appeal|comparison|rational_info|emotional_storytelling|testimonial|scarcity_urgency|nostalgia|aspiration|other"

_SCHEMA = (
    '{"concepts": ['
    '  {"id": "C1",'
    '   "title": "컨셉 제목",'
    '   "hook": "첫 3초 후크 — 시청자를 붙잡는 방식",'
    f'   "appeal_type": "{_APPEAL_TYPE}",'
    '   "strategy_description": "이 컨셉이 소비자를 설득·인상적으로 느끼게 하는 구체적 전략 (1~2문장)",'
    '   "core_tension": "광고가 해소하는 핵심 긴장 또는 욕망",'
    '   "visual_language": "주요 시각 언어·미장센 한 줄",'
    '   "narrative_structure": "서사 구조 (예: PAS·스토리·비교·증언·일상)",'
    '   "distinctiveness_note": "참고 광고들과 명확히 다른 이유"}'
    ' ]}'
)


def _format_lens(label: str, rows: list[dict]) -> str:
    if not rows:
        return ""
    lines = [f"[참고 — {label}]"]
    for ad in rows:
        meta = ad.get("metadata") or {}
        doc = (ad.get("document") or "").strip().replace("\n", " / ")
        lines.append(
            f"- video_id={meta.get('video_id')} appeal={meta.get('appeal_type', '-')} "
            f"execution={meta.get('execution_style', '-')}"
        )
        if doc:
            lines.append(f"  {doc}")
    return "\n".join(lines)


def _format_references(cm3: dict) -> str:
    """CM3 결과(4개 렌즈)를 프롬프트 참고 블록으로 직렬화한다."""
    labels = cm3.get("lens_labels", {})
    lenses = cm3.get("lenses", {})
    blocks = [_format_lens(labels.get(k, k), rows) for k, rows in lenses.items()]
    return "\n\n".join(b for b in blocks if b)


def build_prompt(brief: dict, cm1: dict, cm2: dict, cm3: dict) -> str:
    """브리프+CM1+CM2+CM3(참고 광고)에서 CM4 컨셉 생성 프롬프트를 만든다."""
    brief_text = json.dumps(brief, ensure_ascii=False, indent=2)
    cm1_text = json.dumps(cm1, ensure_ascii=False, indent=2)
    cm2_text = json.dumps(cm2, ensure_ascii=False, indent=2)
    ref_section = _format_references(cm3)
    ref_block = ""
    if ref_section:
        ref_block = (
            "\n[참고 광고 — 4개 관점]\n"
            "주의 — 모방 대상이 아니라 차별화 기준이다. '전략 유사' 참고는 카테고리 관행을 파악하는 용도, "
            "'소구/연출 다각화' 참고는 서로 다른 소구 유형·연출 스타일의 예시일 뿐 정답이 아니다. "
            "각 컨셉의 distinctiveness_note 에 이 참고 광고들과 어떤 점이 다른지 명시해라.\n\n"
            f"{ref_section}\n"
        )
    return (
        "너는 광고 크리에이티브 디렉터다.\n"
        "아래 브리프·카테고리 분석·타겟 전략을 바탕으로 광고 컨셉을 정확히 5개 생성해라.\n\n"
        "규칙 (반드시 준수):\n"
        "1. '좋은 컨셉 1개'가 아니라 '서로 명확히 다른 컨셉 5개'를 만드는 것이 목표다.\n"
        "2. 각 컨셉은 appeal_type·hook·narrative_structure 중 최소 2가지가 달라야 한다.\n"
        "3. 앵커링 방지 — 첫 번째 컨셉에 수렴하지 말고 각 컨셉을 독립적으로 전개해라.\n"
        "4. 이 단계에서 평가·순위·추천은 하지 않는다. 생성만 한다 (선정은 다음 단계).\n\n"
        f"[브리프]\n{brief_text}\n\n"
        f"[CM1 카테고리 분석]\n{cm1_text}\n\n"
        f"[CM2 타겟/포지셔닝]\n{cm2_text}\n"
        f"{ref_block}\n"
        "첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
        f"[출력 스키마]\n{_SCHEMA}"
    )


def run(
    brief: dict,
    cm1: dict,
    cm2: dict,
    cm3: dict,
    *,
    backend: str = "claude",
    gemini_model: str = "",
    codex_model: str | None = None,
) -> dict:
    """참고 광고 기반으로 컨셉 5개(CM4)를 생성한다."""
    return call_llm(
        build_prompt(brief, cm1, cm2, cm3),
        backend=backend, gemini_model=gemini_model, codex_model=codex_model,
    )
