"""클리셰 분석용 크리에이티브 요소 enum 사전 v2 (creative_element_schema.md 구현).

v2: element_type 은 전 산업 공통, subtype 은 공용 사전 + 산업 팩 병합 구조.
클리셰 여부는 적재 시점에 판정하지 않는다 — DB 에는 중립적 요소만 저장하고,
판정은 검색 시점에 세그먼트 내 빈도 집계로 계산한다 (cliche_aggregate.py).
"""
from evaluation.creative.subtypes_common import COMMON_SUBTYPES
from evaluation.creative.subtypes_packs import INDUSTRY_PACKS

# ── profile (세그먼트 검색용 정규화 enum) ──────────────────────────────────────

INDUSTRY_CATEGORIES = ("beauty", "tech_electronics", "entertainment", "fashion_apparel",
                       "health_medical", "food_beverage", "household_care", "other")

PRODUCT_CATEGORY_NORM: dict[str, tuple[str, ...]] = {
    "beauty": ("skincare", "makeup", "haircare", "bodycare", "innerbeauty",
               "beauty_device", "cleansing", "mask", "other"),
    "tech_electronics": ("smartphone_it", "home_appliance", "kitchen_appliance",
                         "av_display", "fitness_equipment", "home_entertainment_device", "other"),
    "entertainment": ("movie", "ott_service", "broadcast_content", "performance",
                      "music_content", "other"),
    "fashion_apparel": ("sportswear", "outerwear", "innerwear", "footwear",
                        "casualwear", "bag_accessory", "other"),
    "health_medical": ("otc_quasi_drug", "health_supplement", "medical_device_procedure",
                       "home_medical_device", "other"),
    "food_beverage": ("instant_noodle", "qsr_burger_chicken", "bakery_dessert", "beverage_soft",
                      "alcohol_beer_soju", "health_functional_food", "dairy_processed_food", "other"),
    "household_care": ("laundry_care", "cleaning_sanitizing", "air_care", "other"),
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
    "fashion_apparel": ("training_wear", "down_jacket", "hiking_wear", "absorbent_underwear",
                        "sneakers", "handbag", "other"),
    "health_medical": ("adhesive_bandage", "health_functional_food", "aesthetic_procedure",
                       "home_medical_device", "other"),
    "food_beverage": ("ramen", "burger", "fried_chicken", "cake_dessert", "carbonated_drink",
                      "beer", "soju", "health_drink", "processed_meat", "other"),
    "household_care": ("fabric_softener", "sanitizing_wipes", "laundry_detergent_booster", "other"),
    "other": ("other",),
}

TARGET_GENDER = ("female", "male", "unisex")
DURATION_BUCKETS = ("15s", "30s", "60s", "other")

# 제품 차별성 축 — usp/positioning 은 concept_evaluation 과 동일 어휘 (교차 조회 호환)
USP_CATEGORY = ("functional_tangible", "emotional_intangible", "economic_price", "other")
POSITIONING_CATEGORY = ("by_product_innovation", "by_service_quality",
                        "by_cost_leadership", "by_target_needs", "other")
PRICE_TIER = ("luxury", "premium", "mid_range", "value", "unknown")

# ── concept reference 전용 (evaluation/concept/concept_evaluation.py 추출 어휘) ─────────────
# usp_category/positioning_category 는 위 USP_CATEGORY/POSITIONING_CATEGORY 를 그대로 재사용한다
# (concept_evaluation.py 주석 그대로 "동일 어휘, 교차 조회 호환"). industry 는 concept_evaluation
# 이 더 넓은 업종을 다뤄(retail_ecommerce/finance 등) production 쪽 INDUSTRY_CATEGORIES 와 별도로 둔다.

CONCEPT_INDUSTRY_CATEGORY = ("beauty", "food_beverage", "retail_ecommerce", "finance", "healthcare",
                             "fashion", "tech_electronics", "automotive", "entertainment", "travel",
                             "education", "gaming", "other")
TARGET_PERSONA_CATEGORY = ("demographic", "psychographic", "behavioral", "other")
APPEAL_TYPE = ("humor", "parody_wordplay", "maternal_love", "vanity", "fear", "sex_appeal",
              "comparison", "rational_info", "emotional_storytelling", "testimonial",
              "scarcity_urgency", "nostalgia", "aspiration", "other")
PERCEIVED_VALUE_CATEGORY = ("functional_quality", "functional_price", "emotional", "social", "other")
MESSAGE_STRATEGY_CATEGORY = ("informational", "transformational", "other")
EXECUTION_STYLE = ("slice_of_life", "scientific_evidence", "fantasy", "fashion", "other")

# M3(컨셉 발산) 전략 렌즈 9종 — generation/v5_m0_m3/prompts/module3.md,
# evaluation/strategy/strategy_schemas.py M3_GUIDE 와 동일 어휘.
# strategy_analysis.json 의 m3.concepts[].lens 는 스키마상 자유 텍스트라(고정 enum 아님)
# 그대로 필터링하면 표기 차이로 어긋난다 — concept_reference_store.py 가 아래로
# 정규화한 뒤 메타데이터에 저장한다.
CONCEPT_LENS = ("twist_taboo_break", "metaphor_analogy", "demo_evidence", "enemy_personification",
               "user_testimonial", "identity_belonging", "functional_job_direct",
               "emotional_job_direct", "comparison_contrast", "other")
CONCEPT_CLAIMTAG = ("C0", "C1", "C2")

# ── casting (casting_direction 요소의 속성 enum) ───────────────────────────────

MAIN_MODEL = ("solo_female", "solo_male", "couple", "group", "ensemble", "hands_only", "none")
AGE_BAND = ("teens", "20s", "30s", "40s+", "variable")
SKIN_LOOK = ("clear_glow", "matte", "pale", "textured", "other")
HAIR = ("long_straight", "wet", "tied_back", "short", "styled", "other")
WARDROBE = ("off_shoulder", "sleeveless", "dress", "casual", "uniform", "formal_suit",
            "costume", "other")

# beauty 외 산업에서는 추출·집계를 생략하는 캐스팅 필드
BEAUTY_ONLY_CASTING = ("skin_look", "hair")

# ── element_type 13종 (영상당 1개 / 다중) ──────────────────────────────────────

SINGLE_TYPES = ("opening_hook", "casting_direction", "narrative_pattern",
                "persuasion_engine", "narrative_form", "tone_register")
MULTI_TYPES = ("sensory_demo_shot", "trust_device", "product_shot",
               "color_light_code", "copy_device", "sound_pattern", "cta_device")
ELEMENT_TYPES = SINGLE_TYPES + MULTI_TYPES

# persuasion_engine/narrative_form/tone_register 어휘 — generation/v5_m0_m3/prompts/module5.md
# (M5 스크립트 설계) L2 설득 엔진·L2.5 서사 형식·L2.6 톤 레지스터 역전과 동일 어휘를 쓴다.
# 이 광고가 M5 를 거쳐 만들어진 게 아니라도, 완성 광고를 이 어휘로 역분류해두면
# M5 가 "이 세그먼트에서 어느 엔진·형식이 이미 많이 쓰였나(recentengines 반-수렴)"를
# 검색으로 확인할 수 있다.
PERSUASION_ENGINE = ("pas", "aida", "bab", "product_demo", "star_story_solution",
                     "four_ps", "social_proof", "unique_mechanism", "fab", "none")
NARRATIVE_FORM = ("linear_mini_drama", "vignette_anthology", "contrast_parallel", "enumeration",
                  "twist", "oneshot_longtake", "pov_first_person", "mockumentary_vox_pop",
                  "metaphor_world", "demo_spectacle", "absurd_exaggeration", "everyday_montage")
TONE_REGISTER_PATTERN = ("heavy_to_comedy", "serious_to_deadpan", "loud_to_flex",
                         "sales_to_documentary", "category_default", "other")

# 해당 요소가 전혀 없으면 'none' 레코드 1개를 기록하는 type (의도적 생략을 집계)
# product_shot 은 무형 서비스 광고(플랫폼 서비스 등) 대응을 위해 포함한다.
NONE_TYPES = ("sensory_demo_shot", "trust_device", "cta_device", "product_shot")

# ── v1 → v2 마이그레이션 매핑 (기존 적재 레코드·분석 파일 흡수) ────────────────

LEGACY_TYPE_MAP = {"texture_shot": "sensory_demo_shot", "model_direction": "casting_direction"}
LEGACY_SUBTYPE_MAP = {"clinical_spec_number": "spec_number", "cg_particle": "process_cg"}
LEGACY_CATEGORY_MAP = {"device": "beauty_device"}


def subtypes_for(industry: str, secondary: str | None = None) -> dict[str, dict[str, str]]:
    """공용 subtype 사전에 주/부 산업 팩을 병합한 enum 가이드를 만든다.

    다트비트(스마트 홈다트)처럼 tech_electronics(하드웨어)+entertainment(게임·대전)
    양쪽 문법이 섞인 광고를 위해, secondary 를 주면 두 산업 팩을 함께 제시한다.
    """
    packs = [INDUSTRY_PACKS.get(industry, {})]
    if secondary and secondary != industry:
        packs.append(INDUSTRY_PACKS.get(secondary, {}))
    return {
        etype: {**COMMON_SUBTYPES[etype], **{k: v for pack in packs for k, v in pack.get(etype, {}).items()}}
        for etype in ELEMENT_TYPES
    }


def infer_industry(product_category_norm: str | None) -> str:
    """industry 미기재 구버전 데이터에서 product_category_norm 으로 산업을 역추정한다."""
    norm = LEGACY_CATEGORY_MAP.get(product_category_norm or "", product_category_norm)
    for industry in ("beauty", "tech_electronics", "entertainment", "fashion_apparel",
                     "health_medical", "food_beverage", "household_care"):
        if norm in PRODUCT_CATEGORY_NORM[industry] and norm != "other":
            return industry
    return "other"


def describe_subtype(element_type: str, subtype: str) -> str:
    """subtype 의 짧은 정의를 공용 사전 + 전 산업 팩에서 찾는다 (리포트 서술용)."""
    if desc := COMMON_SUBTYPES.get(element_type, {}).get(subtype):
        return desc
    for pack in INDUSTRY_PACKS.values():
        if desc := pack.get(element_type, {}).get(subtype):
            return desc
    return subtype


def duration_bucket(duration_sec: float) -> str:
    """근사 길이(±2초)를 표준 버킷으로 정규화한다 (14.5s 등 흡수)."""
    for base, name in ((15, "15s"), (30, "30s"), (60, "60s")):
        if abs(duration_sec - base) <= 2:
            return name
    return "other"
