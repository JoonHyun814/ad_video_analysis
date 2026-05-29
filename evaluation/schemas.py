"""브리프·평가 스키마 상수 및 빌더."""
import json

_BRIEF_SCHEMA = json.dumps({
    "brand": "브랜드명",
    "product": "제품명",
    "ingredients": ["핵심 성분 (없으면 빈 배열)"],
    "functions": ["핵심 기능·효능·장점"],
    "usp": "경쟁 제품과 차별화된 핵심 가치 한 문장",
    "target_age": "타겟 연령대 (예: 20대 초반)",
    "target_persona": "타겟 페르소나 설명 (성별·라이프스타일·이미지)",
    "positioning": "브랜드 포지셔닝 (예: 프리미엄 기능성 뷰티)",
    "slogan": "브랜드 슬로건 또는 핵심 태그라인 (없으면 빈 문자열)",
}, ensure_ascii=False, indent=2)

_CRITERIA: dict[str, list[str]] = {
    "brief_fidelity": [
        "제품의 핵심 성분/기능/효능/장점이 key_messages에 등장하는가",
        "제품 USP가 key_messages로 표현되는가",
        "씬의 분위기·음악·톤이 타겟 연령대/페르소나 감성에 부합하는가",
        "`cast` 캐릭터 연령·이미지 설정이 타겟 연령대/페르소나와 부합하는가",
        "경쟁 브랜드명 또는 직접 비교 표현이 텍스트에 없는가",
    ],
    "message_clarity": [
        "`key_messages`를 소비자가 직관적으로 이해 가능한가",
        "콘티 전체에서 전달하는 메시지가 1~3개 이내로 집중되는가",
    ],
    "brand_positioning": [
        "`concept` 필드에 경쟁 제품과 구별되는 고유한 비주얼 콘셉트가 명시되는가",
        "`concept` → `narrative` → 씬 순서가 동일한 브랜드 포지셔닝을 일관되게 유지하는가",
    ],
    "narrative": [
        "`narrative`가 key_messages, concept을 잘 반영하는가",
        "`narrative` 필드 내용과 실제 씬 구성이 일치하는가",
        "씬 순서에서 서사구조(오프닝 훅 → 문제/감성 자극 → 제품 해결 → 엔딩 CTA)가 확인되는가",
        "씬별 beat description 키워드로 일관된 감정 여정이 형성되는가",
        "씬 간 전환에 시각적·감정적 이유가 있는가 (단순 나열 아님)",
    ],
    "opening_hook": [
        "첫 씬 beat description에 시선 집중·긴장감·궁금증 유발 요소가 포함되는가",
        "'첫 3초가 강렬하다'는 확신이 드는가",
    ],
    "ending": [
        "CTA(Call to Action) 또는 구매 채널 안내가 엔딩 부근에 배치되는가",
    ],
    "dialogue": [
        "`dialogue` beat 텍스트가 자연스럽고 타겟 언어 감성에 맞는가",
        "대사가 과도하게 설명적이지 않는가",
    ],
}


def build_eval_schema() -> str:
    """평가 항목이 미리 채워진 출력 스키마 JSON 문자열을 반환한다."""
    item_template = {"criterion": "", "result": "pass|partial|fail", "score": 1.0, "reasoning": "한국어로 간결하게"}
    categories = {}
    for cat, criteria in _CRITERIA.items():
        items = [{**item_template, "criterion": c} for c in criteria]
        categories[cat] = {"items": items}
    return json.dumps({"categories": categories}, ensure_ascii=False, indent=2)
