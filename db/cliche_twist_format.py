"""클리셰 분석 결과를, 광고 생성 LLM 이 따를 지침(따라야 할 클리셰 / 비트는 방법)으로 포맷한다.

어떤 광고를 참조했는지(video_id·distance 등 식별 정보)는 담지 않는다 — 결과물은
"무엇을 따르고 어떻게 비틀지"에 대한 일반화된 지침이어야 한다.
"""
from evaluation.creative.element_schema import describe_subtype

_ELEMENT_LABELS = {
    "opening_hook": "오프닝 훅", "casting_direction": "인물 연출", "narrative_pattern": "서사 구조",
    "sensory_demo_shot": "감각 시연", "trust_device": "신뢰 장치", "product_shot": "제품 컷",
    "color_light_code": "색·조명", "copy_device": "카피 장치", "sound_pattern": "사운드", "cta_device": "CTA",
}


def _format_header(product_name: str, criteria: str, profile: dict) -> list[str]:
    return [
        f"=== 클리셰 가이드: {product_name} ===",
        "(광고 기획/생성 LLM 참고용 문서. '따라야 할 클리셰'는 이 시장 광고로 인식되기 위해",
        " 지키는 게 안전한 관습이고, '클리셰를 비트는 방법'은 그 관습을 깨 차별화할 지점이다.)",
        f"검색 기준(retrieval_criteria): {criteria}",
        "",
        "[조사된 마케팅 프로필]",
        f"  카테고리: {profile.get('category', '-')}",
        f"  USP     : {profile.get('usp', '-')}",
        f"  타겟    : {profile.get('target', '-')}",
        "",
    ]


def _format_cliche_row(row: dict, n_videos: int) -> list[str]:
    label = _ELEMENT_LABELS.get(row["element_type"], row["element_type"])
    desc = describe_subtype(row["element_type"], row["element_subtype"])
    lines = [
        f"[{row['judgement']}] {label} · {row['element_subtype']} "
        f"({row['video_count']}/{n_videos}편, {row['ratio'] * 100:.0f}%)",
        f"  정의: {desc}",
    ]
    for ex in row["examples"]:
        lines.append(f"  실제 연출 예시: {ex['document']}")
    return lines + [""]


def _format_notable_cliches(n_videos: int, notable: list[dict], total_candidates: int) -> list[str]:
    lines = [
        f"--- 따라야 할 클리셰 (n={n_videos}, 유의미한 조합 {len(notable)}/{total_candidates}건만 선별) ---",
    ]
    for row in notable:
        lines += _format_cliche_row(row, n_videos)
    return lines


def _format_strategy(n_videos: int, strategy: dict) -> list[str]:
    label = _ELEMENT_LABELS.get(strategy["element_type"], strategy["element_type"])
    dominant_desc = describe_subtype(strategy["element_type"], strategy["dominant_subtype"])
    lines = [
        f"[{label}] 관습: '{strategy['dominant_subtype']}'({dominant_desc}) — "
        f"{n_videos}편 중 {strategy['dominant_ratio'] * 100:.0f}%가 사용",
        "  비트는 방법:",
    ]
    for alt in strategy["alternatives"]:
        alt_desc = describe_subtype(strategy["element_type"], alt["subtype"])
        lines.append(f"  → '{alt['subtype']}'({alt_desc})처럼 다른 접근으로 대체")
        if alt["example"]:
            lines.append(f"    실제 사례: {alt['example']}")
    return lines + [""]


def _format_twist_strategies(n_videos: int, strategies: list[dict]) -> list[str]:
    lines = [f"--- 클리셰를 비트는 방법 ({len(strategies)}개 요소) ---"]
    if not strategies:
        return lines + ["  (세그먼트 내 명확한 클리셰 대비 비틀기 사례가 확인되지 않음)", ""]
    for strategy in strategies:
        lines += _format_strategy(n_videos, strategy)
    return lines


def format_report(
    product_name: str,
    criteria: str,
    profile: dict,
    report: dict,
    notable: list[dict],
    total_candidates: int,
    strategies: list[dict],
) -> str:
    """전체 분석 결과를 txt 리포트 문자열로 조립한다."""
    lines = _format_header(product_name, criteria, profile)
    lines += _format_notable_cliches(report["n_videos"], notable, total_candidates)
    lines += _format_twist_strategies(report["n_videos"], strategies)
    return "\n".join(lines)
