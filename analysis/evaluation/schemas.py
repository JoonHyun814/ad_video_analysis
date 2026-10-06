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

# ── Phase 1 🟦 — brief 없이 평가 가능 (🧠 LLM + 🧑 수동) ──────────────────────

_CRITERIA_P1_NO_BRIEF: dict[str, dict[str, str]] = {
    "scene_structure": {
        "scene_length_balance":  "단일 씬이 전체 러닝타임의 30% 이상을 차지하지 않는가",
        "scene_opening_ending":  "오프닝(첫 2초)과 엔딩(마지막 2초)에 각각 독립 씬이 배정됐는가",
    },
    "message_clarity": {
        "message_comprehensibility": "`key_messages`를 한 문장으로 요약했을 때 소비자가 직관적으로 이해 가능한가",
        "message_focus":             "콘티 전체에서 전달하는 메시지가 1~2개 이내로 집중되는가 (과잉 정보 없음)",
        "message_conversion":        "씬별 메시지가 최종 구매 설득으로 수렴하는 구조인가",
        "cta_placement":             "CTA(Call to Action) 또는 구매 채널 안내가 엔딩 부근에 배치됐는가",
    },
    "brand_positioning": {
        "concept_uniqueness":      "`concept` 필드에 경쟁 제품과 구별되는 고유한 비주얼 콘셉트가 명시됐는가",
        "positioning_consistency": "`concept` → `narrative` → 씬 순서가 동일한 브랜드 포지셔닝을 일관되게 유지하는가",
        "persuasion_logic":        "씬 순서에서 성분 → 효능 → 감성 편익으로 이어지는 설득 논리가 드러나는가",
    },
    "narrative": {
        # ── 전체 구조 ──────────────────────────────────────────────────────────
        "narrative_structure":      "씬 순서에서 발단(공감 설정) → 상승행동(갈등 축적) → 절정(브랜드 개입) → 하강행동(결과 입증) → 결말(새로운 균형)의 인과적 흐름이 확인되는가",
        "narrative_scene_match":    "`narrative` 필드 내용과 실제 씬 구성이 일치하는가",
        "narrative_type_fit":       "선택된 내러티브 유형(고전적 드라마 / 생활의 단면 / 비넷 / 퍼포먼스)이 `concept`·`narrative`에 명시된 브랜드 커뮤니케이션 목적에 부합하는가",
        # ── 프라이타그 5단계 씬 역할 ────────────────────────────────────────
        "narrative_exposition":     "발단 씬이 타겟 소비자의 일상과 동일시될 수 있는 현상태(Status Quo)를 설정하며, 불필요한 배경 설명 없이 빠르게 갈등 국면으로 진입하는가",
        "narrative_rising_action":  "상승행동 씬에서 주인공의 결핍·갈등이 점진적으로 축적되어 브랜드 개입의 당위적 공간이 형성되는가",
        "narrative_climax_brand":   "절정 씬에서 브랜드·제품이 단순 화면 노출이 아닌 서사적 전환점(Pivot)의 핵심 도구로 위치하는가 (제품이 '운명을 바꾸는 도구'로 조명되는가)",
        "narrative_brand_result":   "절정 이후 씬에서 브랜드 솔루션의 인과적 결과가 차분하게 입증되어 수용자의 논리적 수용을 이끄는가",
        "narrative_denouement":     "결말 씬이 '새로운 균형' 상태를 제시하며 긍정적 여운을 남겨 브랜드 회상 가능성을 높이는가",
        # ── 자아-브랜드 연결(SBC) ────────────────────────────────────────────
        "consumer_as_hero":         "소비자(주인공)가 서사의 중심이고, 브랜드는 그 여정의 조력자·해결 수단으로 위치하는가 (브랜드 자체가 영웅인 구조가 아닌가)",
        "self_brand_connection":    "씬 묘사에서 주인공이 경험하는 결핍·욕망이 명시적이고, 브랜드·제품이 그 해결의 매개로 인과적으로 연결되는 장면이 존재하는가",
        # ── 감정·톤 흐름 ──────────────────────────────────────────────────────
        "emotion_journey":          "씬별 beat description 키워드로 일관된 감정 여정(예: 긴장→신비→해방→희망)이 형성되는가",
        "scene_transition_reason":  "각 씬 전환 지점에서 앞 씬의 마지막 beat와 다음 씬의 첫 beat 사이에 시각적 또는 감정적 연결 근거가 씬 묘사에 명시됐는가",
        "tone_consistency":         "감정적 단절이나 맥락 없는 톤 전환이 없는가",
    },
    "opening_hook": {
        "opening_hook_elements":    "첫 씬 beat description에 시선 집중·긴장감·궁금증 유발 요소가 포함됐는가",
        "opening_hook_impact":      "첫 씬 묘사에 시각적 대비(색상·크기·속도 반전), 빠른 전환, 또는 질문형·충격형 표현이 최소 1개 이상 명시됐는가",
        "opening_hook_quick_entry": "발단 씬이 과도한 상황 설명 없이 빠르게 대립 국면으로 진입하여 서사적 시간의 팽창(지루함)을 방지하는가",
    },
    "dialogue": {
        "dialogue_naturalness":     "dialogue beat 텍스트가 제품 기능·성분 직접 언급 없이 인물의 감정·상황 중심으로 서술되는가",
        "dialogue_non_descriptive": "등장인물이 카메라를 향해 제품 장점을 직접 설명하는 증언형(Testimonial) 구성이 없이, 극적 행위(Action) 중심으로 이야기가 전달되는가",
    },
    "brand_effect": {
        "visual_concept_color_match": "비주얼 콘셉트(색상·이미지·분위기)가 `production_notes` 컬러 가이드와 텍스트상 일치하는가",
        "series_extensibility":       "이 콘티의 비주얼 언어가 시리즈 확장(다른 제품·시즌)에 재사용 가능한가",
        "brand_continuity":           "브랜드 세계관과 일관된 톤으로 향후 광고와 연속성을 가질 수 있는가",
    },
}

# ── Phase 1 🟧 — brief 비교가 필요한 항목 (🧠 LLM + 🧑 수동) ─────────────────

_CRITERIA_P1_BRIEF: dict[str, dict[str, str]] = {
    "brief_fidelity": {
        "brief_usp_match":         "`key_messages`가 `brief.usp`와 의미적으로 일치하는가",
        "brief_target_tone_match": "씬의 분위기·음악·톤이 `brief.target_age` 감성에 부합하는가",
    },
    "brief_compliance": {
        "brief_no_competitor":      "경쟁 브랜드명 또는 직접 비교 표현이 텍스트에 없는가",
        "brief_required_scenes":    "브리프에서 필수 지정한 장면·슬로건·자막이 씬에 모두 포함됐는가",
        "brief_no_prohibited":      "브리프에서 금지한 표현·이미지가 씬 description에 없는가",
        "brief_cast_persona_match": "`cast` 캐릭터 연령·이미지 설정이 `brief.target_persona`와 부합하는가",
    },
    "brief_strategy": {
        "brief_positioning_no_cheap": "`brief.positioning`이 프리미엄인 경우, 저가 이미지를 주는 요소(과도한 세일·가격 강조 등)가 없는가",
    },
    "brief_dialogue": {
        "brief_dialogue_tone": "`dialogue` beat 텍스트가 `brief.target_age` · `brief.target_persona` 언어 감성에 맞는가",
    },
    "brief_brand_effect": {
        "brief_slogan_match": "슬로건/태그라인이 `brief.slogan` · `brief.positioning`과 논리적으로 부합하는가",
    },
}

# ── Phase 2 — 영상(mp4 / 프레임) 단계 (🧑 수동 검토) ────────────────────────────

_CRITERIA_P2: dict[str, dict[str, str]] = {
    "video_structure": {
        "video_no_jump_cut_error": "컷 전환 시 점프컷 오류·화면 깜박임이 없는가",
    },
    "video_visual_fidelity": {
        "video_cast_appearance":  "모델 외형(연령감·피부·헤어·표정)이 `cast` description과 실제로 일치하는가",
        "video_color_palette":    "컬러 팔레트가 `production_notes` 컬러 가이드와 일치하는가",
        "video_required_scenes":  "브리프에서 지정한 필수 장면이 실제 화면에 명확하게 구현됐는가",
        "video_text_accuracy":    "성분 콜아웃·자막 텍스트가 화면에서 정확히 표기됐는가 (오탈자, 수치 오류 없음)",
    },
    "video_narrative": {
        "video_opening_hook_visual":  "오프닝 2초의 비주얼 훅이 실제로 시선을 끄는가",
        "video_emotion_escalation":   "씬이 진행될수록 감정이 자연스럽게 고조되거나 전환되는가",
        "video_music_cut_sync":       "음악 전환 타이밍이 씬 전환과 실제로 맞물려 있는가",
        "video_signature_shot":       "기억에 남는 시그니처 샷(Signature Shot)이 프레임에서 명확히 식별되는가",
        "video_ending_brand_impact":  "엔딩 비주얼이 브랜드/제품 인상을 강하게 남기는가",
    },
    "video_brand": {
        "video_logo_visibility":       "브랜드 로고의 크기·위치·노출 시간이 충분한 가독성을 확보하는가",
        "video_package_visibility":    "제품 패키지가 왜곡·가림 없이 명확하게 보이는가",
        "video_text_readability":      "자막·text_overlay가 배경 대비 충분한 명도 차이로 읽히는가",
        "video_brand_guidelines":      "브랜드 폰트·컬러 가이드라인이 실제 자막·오버레이에 적용됐는가",
        "video_visual_differentiation":"동일 카테고리 경쟁 광고와 구별되는 독자적 미장센이 실제로 구현됐는가",
    },
}

# ── Phase 3 — 🧠 LLM 평가 항목 (소비자 리서치·자동화 제외) ─────────────────────

_CRITERIA_P3: dict[str, dict[str, str]] = {
    "platform_sentiment": {
        "platform_comment_sentiment": "댓글·반응 텍스트에서 긍정·부정·중립 비율 및 주요 언급 키워드가 브랜드 메시지와 일치하는가",
    },
}


# ── 스키마 빌더 ───────────────────────────────────────────────────────────────

def _build_schema(criteria: dict[str, dict[str, str]]) -> str:
    item_template = {"key": "", "criterion": "", "score": "<0 / 0.25 / 0.5 / 0.75 / 1.0>", "reasoning": "한국어로 간결하게"}
    categories = {}
    for cat, items_dict in criteria.items():
        items = [{**item_template, "key": k, "criterion": c} for k, c in items_dict.items()]
        categories[cat] = {"items": items}
    return json.dumps({"categories": categories}, ensure_ascii=False, indent=2)


def build_eval_schema() -> str:
    """Phase 1 전체 평가 스키마 — brief 포함 (🟦 + 🟧)."""
    return _build_schema({**_CRITERIA_P1_NO_BRIEF, **_CRITERIA_P1_BRIEF})


def build_eval_schema_no_brief() -> str:
    """Phase 1 brief-free 평가 스키마 — brief_* 카테고리 제외 (🟦만)."""
    return _build_schema(_CRITERIA_P1_NO_BRIEF)


def build_eval_schema_video() -> str:
    """Phase 2 영상 평가 스키마."""
    return _build_schema(_CRITERIA_P2)


def build_eval_schema_platform() -> str:
    """Phase 3 플랫폼 감성 분석 스키마."""
    return _build_schema(_CRITERIA_P3)
