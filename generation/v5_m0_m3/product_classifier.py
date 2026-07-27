"""v5_m0_m3 제품 형태·범위 + 관여도 분류기 — 원본 classify_by_rule 그대로 이식.

룰 기반 1차 분류만 사용(원본의 classify_with_llm/classify 는 material_extractor 가
classify_by_rule 을 직접 호출해 M0~M3 경로에서 실제로 쓰이지 않아 이식 대상에서 제외).
"""
from __future__ import annotations

from typing import Any

from generation.v5_m0_m3.schemas import InvolvementLevel, ProductType

_DIGITAL_KEYWORDS = ("SaaS", "saas", "앱", "디지털 서비스", "소프트웨어", "플러그인")
_INTANGIBLE_CATEGORY2 = ("금융", "보험", "교육", "컨설팅", "상담", "구독 서비스")
_PLATFORM_KEYWORDS = ("마켓플레이스", "쿠팡", "배민", "에어비앤비", "당근", "11번가")
_LINE_KEYWORDS = ("라인", "세트", "시리즈", "컬렉션", "패키지")

_HIGH_INVOLVEMENT_CATEGORY2 = ("금융", "보험", "자동차", "부동산", "B2B")
_LOW_INVOLVEMENT_CATEGORY2 = ("식품", "스낵", "생활용품", "잡화")

_VIS_RESULT_CAT = ("건기식", "건강기능", "다이어트", "교육", "헬스", "영양")
_VIS_INVISIBLE_CAT = ("보험", "통신", "멤버십", "금융", "카드", "은행", "구독")
_BENEFIT_EMOTIONAL_CAT = ("럭셔리", "향수", "주얼리", "여행", "엔터", "공연", "뷰티")


def _has_any(text: str, keywords: tuple[str, ...]) -> bool:
    if not text:
        return False
    low = text.lower()
    return any(k.lower() in low for k in keywords)


def _classify_producttype(raw: dict[str, Any]) -> ProductType:
    productname = raw.get("productname") or ""
    brand = raw.get("brand") or ""
    category2name = raw.get("category2name") or ""
    category3name = raw.get("category3name") or ""
    productfeatures = raw.get("productfeatures") or ""
    images = raw.get("productimageurls") or []

    cat_blob = f"{category2name} {category3name}"
    text_blob = f"{productname} {productfeatures}"

    if _has_any(text_blob, _PLATFORM_KEYWORDS) or _has_any(productfeatures, _PLATFORM_KEYWORDS):
        return ProductType.PLATFORM
    if _has_any(cat_blob, _DIGITAL_KEYWORDS) or _has_any(text_blob, _DIGITAL_KEYWORDS):
        return ProductType.DIGITALPRODUCT
    if _has_any(category2name, _INTANGIBLE_CATEGORY2):
        return ProductType.INTANGIBLESERVICE
    if _has_any(productname, _LINE_KEYWORDS) and len(images) >= 2:
        return ProductType.PRODUCTLINE
    if not images and brand and brand.strip().lower() == productname.strip().lower():
        return ProductType.BRAND
    return ProductType.SINGLEPRODUCT


def _classify_involvement(raw: dict[str, Any]) -> InvolvementLevel:
    category2name = raw.get("category2name") or ""
    pricerange = raw.get("pricerangeest") or ""

    if _has_any(category2name, _HIGH_INVOLVEMENT_CATEGORY2):
        return InvolvementLevel.HIGH
    if pricerange == "under50k" and _has_any(category2name, _LOW_INVOLVEMENT_CATEGORY2):
        return InvolvementLevel.LOW
    return InvolvementLevel.MEDIUM


def _classify_visibility(raw: dict[str, Any], pt: ProductType) -> str:
    cat = f"{raw.get('category2name') or ''} {raw.get('category3name') or ''} {raw.get('industry') or ''}"
    if pt == ProductType.DIGITALPRODUCT:
        return "ui"
    if pt == ProductType.BRAND:
        return "mood"
    if _has_any(cat, _VIS_INVISIBLE_CAT):
        return "invisible"
    if _has_any(cat, _VIS_RESULT_CAT):
        return "result_only"
    return "fully"


def _classify_benefit_type(raw: dict[str, Any]) -> str:
    cat = f"{raw.get('category2name') or ''} {raw.get('category3name') or ''} {raw.get('industry') or ''}"
    if _has_any(cat, _BENEFIT_EMOTIONAL_CAT):
        return "emotional"
    return "functional"


def _derive_producttype7(pt: ProductType, vis: str, inv: InvolvementLevel) -> str:
    if pt == ProductType.BRAND:
        return "G"
    if pt == ProductType.DIGITALPRODUCT:
        return "D"
    if pt == ProductType.PRODUCTLINE:
        return "C"
    if pt in (ProductType.INTANGIBLESERVICE, ProductType.PLATFORM):
        return "F" if inv == InvolvementLevel.HIGH else "E"
    return "B" if vis == "result_only" else "A"


def classify_by_rule(raw: dict[str, Any]) -> dict[str, Any]:
    """룰 기반 4축 분류 결과 dict (producttype/involvementlevel/visibility/benefittype/producttype7/confidence)."""
    pt = _classify_producttype(raw)
    inv = _classify_involvement(raw)
    vis = _classify_visibility(raw, pt)
    bt = _classify_benefit_type(raw)
    t7 = _derive_producttype7(pt, vis, inv)

    has_cat = bool(raw.get("category2name") or raw.get("category3name"))
    has_features = bool(raw.get("productfeatures"))
    confidence = 0.4 + (0.3 if has_cat else 0.0) + (0.3 if has_features else 0.0)

    return {
        "producttype": pt,
        "involvementlevel": inv,
        "visibility": vis,
        "benefittype": bt,
        "producttype7": t7,
        "classifierconfidence": round(confidence, 2),
    }
