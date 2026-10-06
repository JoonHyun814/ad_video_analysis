"""도메인별 VL 분류 프롬프트 정의."""
from __future__ import annotations

DOMAIN_LABELS: dict[str, list[str]] = {
    "angle": ["탑뷰", "드론샷", "로우앵글", "아이레벨", "하이앵글", "더치앵글"],
    "shot_size": ["익스트림클로즈업", "클로즈업", "미디엄클로즈업", "미디엄샷", "롱샷", "와이드샷", "풀샷"],
    "lighting": ["역광", "실루엣", "로우키", "하이키", "흑백", "레트로", "일반조명"],
    "focus": ["아웃포커스", "딥포커스", "랙포커스", "소프트포커스", "팬포커스"],
}

_DOMAIN_DESC: dict[str, str] = {
    "angle": "카메라 앵글(시점)",
    "shot_size": "샷 크기(프레이밍)",
    "lighting": "조명 유형·톤",
    "focus": "포커스 스타일",
}

_LABEL_DESC: dict[str, str] = {
    "탑뷰": "카메라가 피사체 바로 위에서 수직으로 내려다보는 앵글",
    "드론샷": "드론·항공 장비로 높은 곳에서 이동하며 촬영",
    "로우앵글": "카메라가 피사체 아래에서 위를 올려다보는 앵글",
    "아이레벨": "피사체와 같은 눈높이의 표준 앵글",
    "하이앵글": "카메라가 피사체보다 높은 위치에서 내려다보는 앵글",
    "더치앵글": "카메라를 기울여 수평이 비스듬한 앵글",
    "익스트림클로즈업": "눈·입술·제품 질감 등 일부가 프레임을 꽉 채우는 극단적 근접 샷",
    "클로즈업": "인물 얼굴 전체 또는 제품 전체가 프레임 대부분을 차지",
    "미디엄클로즈업": "가슴 위 정도까지 보이는 샷",
    "미디엄샷": "허리 위 정도까지 보이는 샷",
    "롱샷": "인물 전신이 보이고 배경도 상당히 보이는 샷",
    "와이드샷": "인물보다 배경·환경이 넓게 보이는 샷",
    "풀샷": "머리부터 발끝까지 인물 전신이 딱 맞게 보이는 샷",
    "역광": "광원이 피사체 뒤에 있어 림라이트·플레어·후광이 생기는 조명",
    "실루엣": "밝은 배경 앞에서 피사체가 검은 형태로만 보이는 상태",
    "로우키": "화면 대부분이 어둡고 강한 명암 대비가 있는 톤",
    "하이키": "화면 전체가 밝고 그림자가 적은 화사한 톤",
    "흑백": "프레임 대부분이 무채색·모노크롬",
    "레트로": "VHS 노이즈·빈티지 색감 등 과거 시대 미감을 의도적으로 재현",
    "일반조명": "위 특수 조명에 해당하지 않는 일반적 조명",
    "아웃포커스": "배경이 흐릿하고 피사체만 선명한 얕은 피사계 심도",
    "딥포커스": "전경·배경 모두 선명하게 초점이 맞는 깊은 피사계 심도",
    "랙포커스": "촬영 중 초점 대상이 한 피사체에서 다른 피사체로 이동",
    "소프트포커스": "전체적으로 약간 흐릿하고 부드러운 포커스",
    "팬포커스": "화면 전체가 균일하게 선명한 포커스",
}


def build_prompt(domain: str) -> str:
    """단일 도메인 분류 프롬프트 생성."""
    labels = DOMAIN_LABELS[domain]
    desc = _DOMAIN_DESC[domain]
    items = "\n".join(f"- {lbl}: {_LABEL_DESC.get(lbl, '')}" for lbl in labels)
    label_list = ", ".join(f'"{lbl}"' for lbl in labels)
    return (
        f"이 이미지의 {desc}을 분류하세요.\n\n"
        f"선택지:\n{items}\n\n"
        f"다음 중 하나만 답하세요: {label_list}\n"
        f"레이블 이름만 출력하세요. 설명 불필요."
    )


def build_multi_prompt(domains: list[str]) -> str:
    """여러 도메인을 한 번에 분류하는 프롬프트 생성."""
    sections = []
    for domain in domains:
        desc = _DOMAIN_DESC[domain]
        labels = " | ".join(DOMAIN_LABELS[domain])
        sections.append(f"[{desc}] {labels}")

    answer_fmt = "\n".join(f"{d}: <레이블>" for d in domains)
    return (
        "이 이미지를 아래 항목별로 분류하세요.\n\n"
        + "\n".join(sections)
        + "\n\n반드시 아래 형식으로만 답하세요:\n"
        + answer_fmt
    )


def parse_multi_response(text: str, domains: list[str]) -> dict[str, str]:
    """멀티 도메인 응답 텍스트를 파싱해 {domain: label} 반환."""
    import re
    result: dict[str, str] = {}
    for domain in domains:
        valid = DOMAIN_LABELS[domain]
        m = re.search(rf'{re.escape(domain)}\s*:\s*(\S+)', text, re.IGNORECASE)
        raw = m.group(1).rstrip('.,;:') if m else ""
        if raw in valid:
            result[domain] = raw
        else:
            result[domain] = next((lbl for lbl in valid if lbl in text), valid[0])
    return result
