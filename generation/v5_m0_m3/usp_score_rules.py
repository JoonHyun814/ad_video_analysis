"""usp_score_service.py 발췌 — page_section_ocr._score_other 가 쓰는 clarity 룰 + proof 신호만 이식.

원본의 LLM 의미축(relevance/differentiation/demonstrability, score_usps 진입점)은 M0 경로에서
호출되지 않는다(material_extractor 는 uspscoring=False 로 호출) — 이식 대상에서 제외.
"""
from __future__ import annotations

import re

_VAGUE_KEYWORDS = (
    "최고", "최강", "완벽", "혁명", "최초", "유일",
    "엄청난", "대박", "끝판왕",
)
_GENERIC_KEYWORDS = (
    "간편", "편리", "믿을 수 있는", "믿을수있는", "특별한",
    "합리적", "다양한", "프리미엄", "스마트한", "퀄리티",
)

# proof 신호 3분류 (DR-CTV: objective_proof / testimony / authority).
_OBJECTIVE_PROOF = (
    "임상", "시험", "인증", "특허", "검증", "데이터", "함량", "테스트",
    "fda", "식약처", "논문", "연구", "%", "퍼센트",
)
_TESTIMONY = ("후기", "체험", "리뷰", "재구매", "만족도")
_AUTHORITY = ("전문가", "의사", "약사", "피부과", "공동개발", "수상", "1위", "추천")


def _clarity(text: str) -> float:
    """명확성 룰 — 길이/모호어/범용어 + 명사·수치 보너스."""
    t = (text or "").strip()
    if not t:
        return 0.0
    nwords = len(t.split())
    nchars = len(t)
    if 5 <= nwords <= 12 and 10 <= nchars <= 30:
        length = 1.0
    elif 3 <= nwords <= 16 and 7 <= nchars <= 40:
        length = 0.7
    elif nwords <= 2 or nchars < 7:
        length = 0.4
    elif nwords >= 25 or nchars >= 80:
        length = 0.3
    else:
        length = 0.55
    vague = min(sum(1 for k in _VAGUE_KEYWORDS if k in t) * 0.15, 0.4)
    generic = min(sum(1 for k in _GENERIC_KEYWORDS if k in t) * 0.1, 0.25)
    base = max(length - vague - generic, 0.0)
    bonus = 0.1 if re.search(r"\d", t) else 0.0
    return min(base + bonus, 1.0)
