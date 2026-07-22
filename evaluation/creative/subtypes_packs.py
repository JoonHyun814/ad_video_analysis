"""산업별 subtype 확장 팩 (v2). 공용 사전은 subtypes_common.py 참조.

추출 시 industry_category 에 해당하는 팩을 공용 사전에 병합해 enum 가이드를 만든다.
집계는 세그먼트(=산업 필터) 내부에서만 이루어지므로 팩 간 subtype 충돌은 없다.
"""

INDUSTRY_PACKS: dict[str, dict[str, dict[str, str]]] = {
    "beauty": {
        "opening_hook": {
            "object_macro": "상징 오브제(원료 식물·장식함 등) 매크로로 시작",
            "face_closeup_dark": "어두운 화면에서 얼굴이 서서히 드러나는 클로즈업",
            "face_closeup_backlight": "역광·확산광이 감싸는 얼굴 클로즈업",
            "silhouette_backlight": "역광 검은 실루엣(얼굴 미노출)로 시작",
        },
        "casting_direction": {
            "neutral_to_gaze": "시선 회피·고개 숙임 → 정면 응시 전환",
            "eyes_closed_to_open": "눈 감음 → 눈 뜨며 응시 (각성 은유)",
            "silhouette_to_gaze": "실루엣 → 점진적 얼굴 공개",
        },
        "sensory_demo_shot": {
            "cream_swirl": "용기 속 크림 소용돌이/회오리 매크로",
            "liquid_macro": "액체·에센스·오일 극단 매크로",
            "bubble_macro": "투명 액체 속 기포·산란광 매크로",
            "droplet_on_skin": "촉촉한 피부 위 물방울·에센스 클로즈업",
            "application_closeup": "도포·펌프 등 실사용 동작 초근접",
            "skin_graphic_overlay": "얼굴 위 성분 작용·피부 조직 그래픽 합성",
        },
        "trust_device": {
            "ingredient_claim": "독자 성분명·원료 스토리 강조",
        },
        "product_shot": {
            "open_texture_reveal": "뚜껑 열리며 내용물·내부 조명 공개",
        },
        "copy_device": {
            "transformation_phrase": "'다시 태어나다·되돌리다'류 재생 상투구",
            "time_motif": "'시간' 철학 모티프 카피",
            "essence_motif": "'피부 본연·근본·자생력'류 본질 회귀 상투구",
            "archaic_tone": "고어체·경전체 특수 어투",
        },
    },
    "tech_electronics": {
        "sensory_demo_shot": {
            "operation_macro": "작동·처리 과정(분쇄·흡입 등) 매크로",
            "performance_demo": "물리 성능 실물 시연 (흡입력·출력 등)",
            "output_dispense_shot": "토출·출력물 클로즈업 (온수 김·물줄기 등)",
            "mechanism_closeup": "내부 구조·부품 정지 클로즈업",
            "exploded_assembly_cg": "부품 분해·조립(exploded view) CG",
            "spec_infographic_overlay": "제품 위 수치·각도 인포그래픽 합성",
            "ui_demo_shot": "기기 화면 UI 조작 시연",
            "result_transformation": "처리 전후 결과물 변환 제시",
        },
        "trust_device": {
            "engineering_reveal": "내부 메커니즘 노출로 기술력 증명",
        },
        "product_shot": {
            "form_factor_transform": "접힘·변형 등 폼팩터 전환 시연",
        },
    },
    "entertainment": {
        "casting_direction": {
            "ip_character_footage": "IP 캐릭터·본편 연기 발췌 (광고용 연출 아님)",
        },
        "narrative_pattern": {
            "footage_montage": "본편 발췌 하이라이트 몽타주→타이틀→고지",
            "content_catalog": "콘텐츠 IP 를 컷당 1개씩 나열하는 카탈로그 구성",
            "teaser_reveal": "의미 은닉→정체 공개→고지의 티저 구성",
        },
        "sensory_demo_shot": {
            "content_clip_showcase": "콘텐츠 본편 클립 발췌 쇼케이스",
            "spectacle_vfx": "스펙터클·VFX 물량 샷",
        },
        "trust_device": {
            "studio_ip_authority": "제작사·프랜차이즈 로고 권위",
            "format_badge": "IMAX·4DX·Dolby 등 상영 포맷 뱃지",
            "content_lineup": "인기 IP 라인업 제시",
            "license_note": "자료제공·라이선스 고지",
        },
        "product_shot": {
            "title_card": "타이틀 카드 리빌 (로고 엔드카드와 구분)",
        },
        "copy_device": {
            "release_date_copy": "개봉·공개 시점 반복 고지 카피",
        },
    },
    "other": {},
}
