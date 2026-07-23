"""클리셰 분석용 크리에이티브 요소 enum 사전 v2 (creative_element_schema.md 구현).

v2: element_type 은 전 산업 공통, subtype 은 공용 사전 + 산업 팩 병합 구조.
클리셰 여부는 적재 시점에 판정하지 않는다 — DB 에는 중립적 요소만 저장하고,
판정은 검색 시점에 세그먼트 내 빈도 집계로 계산한다 (cliche_aggregate.py).
"""
from evaluation.creative.subtypes_common import COMMON_SUBTYPES
from evaluation.creative.subtypes_packs import INDUSTRY_PACKS

# ── profile (세그먼트 검색용 정규화 enum) ──────────────────────────────────────

INDUSTRY_CATEGORIES = ("beauty", "tech_electronics", "entertainment", "other")

PRODUCT_CATEGORY_NORM: dict[str, tuple[str, ...]] = {
    "beauty": ("skincare", "makeup", "haircare", "bodycare", "innerbeauty",
               "beauty_device", "cleansing", "mask", "other"),
    "tech_electronics": ("smartphone_it", "home_appliance", "kitchen_appliance",
                         "av_display", "fitness_equipment", "home_entertainment_device", "other"),
    "entertainment": ("movie", "ott_service", "broadcast_content", "performance",
                      "music_content", "other"),
    "other": ("other",),
}

PRODUCT_SUBTYPE: dict[str, tuple[str, ...]] = {
    "beauty": ("essence_serum", "cream", "ampoule", "lotion", "toner", "eye_care", "sun_care",
               "cushion_foundation", "shampoo", "body_wash", "mask_pack", "beauty_device",
               "supplement", "other"),
    "tech_electronics": ("smartphone", "wearable", "tv_display", "vacuum", "water_purifier",
                         "air_care", "kitchen_appliance", "massage_chair", "fitness_equipment",
                         "leisure_device", "other"),
    "entertainment": ("theatrical_release", "ott_subscription", "series_content",
                      "live_performance", "exhibition", "music_release", "other"),
    "other": ("other",),
}

TARGET_GENDER = ("female", "male", "unisex")
DURATION_BUCKETS = ("15s", "30s", "60s", "other")

# 제품 차별성 축 — usp/positioning 은 concept_evaluation 과 동일 어휘 (교차 조회 호환)
USP_CATEGORY = ("functional_tangible", "emotional_intangible", "economic_price", "other")
POSITIONING_CATEGORY = ("by_product_innovation", "by_service_quality",
                        "by_cost_leadership", "by_target_needs", "other")
PRICE_TIER = ("luxury", "premium", "mid_range", "value", "unknown")

# ── casting (casting_direction 요소의 속성 enum) ───────────────────────────────

MAIN_MODEL = ("solo_female", "solo_male", "couple", "group", "ensemble", "hands_only", "none")
AGE_BAND = ("teens", "20s", "30s", "40s+", "variable")
SKIN_LOOK = ("clear_glow", "matte", "pale", "textured", "other")
HAIR = ("long_straight", "wet", "tied_back", "short", "styled", "other")
WARDROBE = ("off_shoulder", "sleeveless", "dress", "casual", "uniform", "formal_suit",
            "costume", "other")

# beauty 외 산업에서는 추출·집계를 생략하는 캐스팅 필드
BEAUTY_ONLY_CASTING = ("skin_look", "hair")

# ── element_type 10종 (영상당 1개 / 다중) ──────────────────────────────────────

SINGLE_TYPES = ("opening_hook", "casting_direction", "narrative_pattern")
MULTI_TYPES = ("sensory_demo_shot", "trust_device", "product_shot",
               "color_light_code", "copy_device", "sound_pattern", "cta_device")
ELEMENT_TYPES = SINGLE_TYPES + MULTI_TYPES

# 해당 요소가 전혀 없으면 'none' 레코드 1개를 기록하는 type (의도적 생략을 집계)
NONE_TYPES = ("sensory_demo_shot", "trust_device", "cta_device")

# ── v1 → v2 마이그레이션 매핑 (기존 적재 레코드·분석 파일 흡수) ────────────────

LEGACY_TYPE_MAP = {"texture_shot": "sensory_demo_shot", "model_direction": "casting_direction"}
LEGACY_SUBTYPE_MAP = {"clinical_spec_number": "spec_number", "cg_particle": "process_cg"}
LEGACY_CATEGORY_MAP = {"device": "beauty_device"}


def subtypes_for(industry: str) -> dict[str, dict[str, str]]:
    """공용 subtype 사전에 산업 팩을 병합한 enum 가이드를 만든다."""
    pack = INDUSTRY_PACKS.get(industry, {})
    return {
        etype: {**COMMON_SUBTYPES[etype], **pack.get(etype, {})}
        for etype in ELEMENT_TYPES
    }


def infer_industry(product_category_norm: str | None) -> str:
    """industry 미기재 구버전 데이터에서 product_category_norm 으로 산업을 역추정한다."""
    norm = LEGACY_CATEGORY_MAP.get(product_category_norm or "", product_category_norm)
    for industry in ("beauty", "tech_electronics", "entertainment"):
        if norm in PRODUCT_CATEGORY_NORM[industry] and norm != "other":
            return industry
    return "other"


def duration_bucket(duration_sec: float) -> str:
    """근사 길이(±2초)를 표준 버킷으로 정규화한다 (14.5s 등 흡수)."""
    for base, name in ((15, "15s"), (30, "30s"), (60, "60s")):
        if abs(duration_sec - base) <= 2:
            return name
    return "other"
