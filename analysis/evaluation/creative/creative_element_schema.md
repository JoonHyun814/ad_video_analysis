# creative_element_schema — 클리셰 분석용 크리에이티브 요소 스키마

카테고리 세그먼트(예: 스킨케어 15초) 내 광고들의 클리셰/클리셰 파괴 요소를 정량 분석하기 위한
vectorDB 스키마·enum 사전. `scenario_analysis.json` → LLM 추출 → ChromaDB 적재 → 세그먼트 검색 →
요소 집계의 파이프라인을 전제로 한다.

## 설계 원칙

1. **클리셰 여부는 적재 시점에 판정하지 않는다.** 클리셰는 세그먼트 내 상대적 빈도이므로,
   DB에는 중립적인 요소만 저장하고 판정은 검색 시점 집계로 계산한다.
2. **영상 단위 + 요소 단위 2계층 저장.** 요소 1개 = 레코드 1개여야 "무엇이 비슷한지"가 쿼리로 나온다.
3. **enum 정규화 + 원문 병기.** 자유 문자열 카테고리는 exact 필터를 깨뜨린다 (예: "스킨케어 (세럼)" 변형).
4. **(v2) element_type 은 전 산업 공통, subtype 은 공용 + 산업 팩.** 스키마를 산업별로 통째로
   분리하면 산업 관통 클리셰(sfx_cut_sync·double_coding 등) 교차 비교가 불가능해진다.
   판정이 세그먼트(=산업 필터) 내부 빈도이므로 subtype 사전만 산업별로 확장해도 집계는 성립한다.

## v2 개정 요약 (2026-07-22) — 산업 팩 구조

ent 3편(419·420·421) + tech 7편(42·57·78·119·205·361·498) 검증 결과, type 골격은 산업을 관통하지만
(재사용률 ~70%) 일부 type 의 뷰티 전제와 profile enum 붕괴(비뷰티 전부 `other`)가 확인되어 개정.

| 변경 | v1 | v2 |
|------|----|----|
| type 개명 | `texture_shot` (제형 전제) | `sensory_demo_shot` — 뷰티=제형, tech=성능·작동 시연, ent=콘텐츠 클립 |
| type 개명 | `model_direction` (표정 아크 전제) | `casting_direction` — 스포크스퍼슨·동작 시연·앙상블·`none`(인물 미등장) 수용 |
| type 신설 | — | `cta_device` (multi, none 허용) — 검색 유도·커머스 UI·가격 오퍼·출시 고지 |
| subtype 구조 | 단일 사전 | `subtypes_common.py`(공용) + `subtypes_packs.py`(beauty/tech_electronics/entertainment 팩) 병합 |
| profile | product_category_norm 뷰티 단일 enum | `industry_category` 필수 승격(세그먼트 1차 키) + 산업별 product_category_norm/product_subtype enum |
| 개명 | `device` (미용기기) | `beauty_device` — 가전과 이름 충돌 방지 |
| casting | 전 필드 공통 | `skin_look`/`hair` 는 beauty 전용(비뷰티 추출·집계 생략), MAIN_MODEL `ensemble`/`hands_only`/`none`, WARDROBE `formal_suit`/`costume` 추가 |
| profile | industry 단일값 | `industry_secondary`(부산업, optional) 추가 — 두 산업 팩을 함께 병합해 추출하고, 리포트는 주/부 산업 어느 쪽 필터에도 매칭(`$or`). `product_category_norm` 은 주산업 enum 1개로 유지(콤마 결합 안 함) |
| 마이그레이션 | — | `LEGACY_TYPE_MAP`/`LEGACY_SUBTYPE_MAP`(clinical_spec_number→spec_number, cg_particle→process_cg)/`LEGACY_CATEGORY_MAP` 을 적재 시 자동 적용 — v1 분석 파일 재추출 불필요 |

## v2.1 개정 요약 (2026-07-23) — 산업 팩 확장

15초 세그먼트 유사도 검색으로 뽑힌 22편(뷰티 8·패션의류 4·식음료 4·헬스케어/플랫폼 6)의
scenario_analysis 를 스키마 적합성 검토한 결과 반영.

| 변경 | 내용 |
|------|------|
| 산업 팩 신설 | `fashion_apparel` — `product_shot.wearing_styling_shot`(착용 상태 룩북형 워킹·포즈 샷). 근거: 아디다스·EIDER 2편·디펜드 스타일 4편 전부에서 반복, 기존 `model_holding`/`in_context_placement` 로는 "착용"을 못 담음 |
| 산업 팩 신설 | `health_medical` — `casting_direction.body_part_only`(얼굴 없이 신체 부위만 등장), `trust_device.regulatory_review_notice`/`non_medical_device_disclaimer`(의료기기 광고심의필·비의료기기 면책 고지 — 기존 `certification_note` 하나로 뭉뚱그려지던 법적 성격이 다른 고지문 분리), `cta_device.booking_reservation_cta`(체험·상담 예약 유도) |
| beauty 팩 확장 | `sensory_demo_shot.concept_time_metaphor_cg` — 시간·순환 등 추상 개념 메타포 CG (제품 작동 원리와 무관, 기존 `process_cg` 정의로는 못 담음). 설화수 자음생/윤조 계열에서 반복 |
| `NONE_TYPES` 확장 | `product_shot` 추가 (기존 sensory_demo_shot/trust_device/cta_device 3종 → 4종). 생활 플랫폼 서비스처럼 물리 제품이 없는 무형 서비스 광고의 "의도적 생략"을 기록하기 위함 |
## v2.2 개정 요약 (2026-07-23) — food_beverage 팩 신설

v2.1에서 보류했던 `food_beverage` 를 라면 3편·QSR(버거·치킨) 6편·맥주/소주 3편·베이커리 2편·건기식음료 3편
(총 17편) 추가 검증 후 신설. **표본 2편 이상 확인된 항목만 반영**(fashion_apparel/health_medical 과 동일 기준).

| element_type | subtype | 근거 |
|---|---|---|
| sensory_demo_shot | `steam_rise_macro` (김 클로즈업) | 라면 3편 + 맥주군 예비조사 1편, 총 4편 |
| sensory_demo_shot | `bite_cross_section` (베어문 단면) | 버거 2편 |
| sensory_demo_shot | `topping_drizzle_pour` (소스·시럽 흐름) | 치킨 2편 + 아이스크림 예비조사 1편 |
| sensory_demo_shot | `tasting_bite_closeup` (베어물기·삼킴 클로즈업) | 베이커리 2편 |
| sensory_demo_shot | `noodle_lift_macro` (면 들어올리기) | 라면 2편 |
| casting_direction | `toast_cheers_gesture` (건배 제스처) | 맥주 2편 |
| cta_device | `direct_order_cta` (전화번호·문구 즉시 주문 유도) | 치킨 2편 |

**표본 부족으로 보류한 후보** (1편 근거만 확인, 향후 표본 확충 시 재검토):
`shell_crack_reveal`(셸 파열 공개), `foam_carbonation_pour`(거품·탄산 붓기 — 맥주 3편 표본에서 오히려 미확증),
`ingredient_drop_splash`/`broth_full_drink_demo`/`plated_dish_hero_shot`(라면), `liquid_pour_macro`/`carbonation_burst`(음료),
`ingredient_process_claim`/`food_label_disclaimer`(trust_device), `nostalgia_flashback_open`(라면 오프닝).
`ingredient_layer_reveal` 은 `bite_cross_section` 에 흡수.

버거군과 치킨군은 sensory_demo_shot 하위 문법이 뚜렷이 갈렸으나(단면 시식 증명형 vs 소스 코팅형),
element_type 골격은 공유하므로 별도 서브 산업 팩까지는 신설하지 않았다.

`cta_device.social_challenge_cta`(SNS 챌린지·해시태그 참여 유도, QSR 1편 근거)는 특정 산업에 국한될
근거가 없어 산업 팩이 아니라 `subtypes_common.py` 공용 사전으로 바로 승격했다.

**건기식/기능성 음료의 industry 태깅**: 정관장·뉴케어·고려은단처럼 `product_category_norm=health_functional_food`
인 `food_beverage` 광고가 의료기기 심의번호·비의료기기 면책 등 `health_medical` 특유의 trust_device 소구를
쓰는 경우, `industry_category=food_beverage` + `industry_secondary=health_medical` 로 추출하면
두 팩의 subtype 이 함께 병합되어 `--industry_secondary health_medical` 로 개별 지정할 수 있다
(다트비트식 복합 산업 처리와 동일 메커니즘, `run.py::_run_extract` 참고). 이번 3편(52·264·471)은
health_medical 특유의 규제 고지가 나타나지 않아 secondary 없이 처리했다.

## v2.3 개정 요약 (2026-07-24) — household_care 팩 신설 + 공용/health_medical 확장

세스코(방역·위생 서비스) 유사도 검색으로 뽑힌 26편(헬스케어 다수·뷰티·생활용품 4편)의 scenario_analysis
검토 결과 반영. **표본 2편 이상 확인된 항목만 반영**(기존 산업 팩과 동일 기준).

| element_type | subtype | 위치 | 근거 |
|---|---|---|---|
| sensory_demo_shot | `scent_diffusion_fx` (후각 대체 CG: 꽃잎·빛입자·후광) | household_care(신설) | Clorox 센티바, Downy(실내건조/화이트머스크) |
| sensory_demo_shot | `germ_dirt_removal_demo` (세균·오염 캐릭터화 격파·소멸 시연) | household_care(신설) | Clorox 센티바, 피지 모락셀라 |
| opening_hook | `mood_mystery_open` (제품·문제 제시 없이 분위기만으로 시작) | subtypes_common(공용) | cêpoLAB 세포랩, 세라젬 밸런스 |
| opening_hook | `copy_driven_declaration_open` (선언적 카피 문장만으로 시작) | health_medical | O2ON, 디펜드 스타일. *근거 다소 약함(텍스트모핑 vs 보이스오버로 집행 방식 상이) — 향후 표본 확충 시 재검토* |
| trust_device | `ascending_number_reveal` (신뢰 수치 카운트업 애니메이션) | subtypes_common(공용) | Clorox 센티바, 센트룸, 듀오락 골드 |
| trust_device | `regulatory_disclosure_notice` (건기식 등 산업 전반 법정 광고고지, 의료기기 한정 아님) | subtypes_common(공용) | 익수공진단, GC녹십자 비맥스 (보조: Downy, 코웨이, Clorox) |
| copy_device | `progressive_caption_buildup` (자막이 순차 누적되며 문장 완성) | health_medical | 익수공진단, 세라젬 밸런스, GC녹십자 비맥스 |
| copy_device | `dual_claim_framing` (서로 다른 두 효능을 하나의 통합 가치로 결합) | health_medical | Will(한국야쿠르트), 엘레나, 센트룸 |

**신규 산업 `household_care`**: category_analysis.json 상 이 클러스터는 `retail_ecommerce`/`other` 로
흩어져 있는데, 두 값 모두 household_care 외 다른 산업에도 쓰이는 catch-all 이라 `run.py::_CATEGORY_INDUSTRY_ALIAS`
에 자동 별칭을 추가하지 않았다. 추출 시 `--industry_secondary household_care` 로 수동 지정한다.

**표본 부족으로 보류한 후보** (1편 근거만 확인, 향후 표본 확충 시 재검토):
제품 소진 타임랩스(치킨), 전신 래핑 리본 FX(엘레나), RCT 임상시험 설계 상세공개(듀오락 골드),
ESG 누적임팩트 수치(코웨이), 비예약형 전문가 리다이렉트(GC녹십자), QR코드 오버레이(드시모네 4500),
실사+카툰필터 합성 리액션(GC녹십자), 흑백+스팟컬러 그레이딩(링티), 푸른 번개 이펙트 라이팅(GC녹십자),
공중 도킹/조립 리빌(뷰라셀), 주술/고어체 카피(세포랩), 서브브랜드 단계적 업그레이드 릴레이 구조(GC녹십자),
워드모프 타이틀(O2ON).

판정 기준(60%/30%/고립)과 컬렉션 2개 구조는 변경 없음. 아래 enum 사전은 v1(뷰티 기준) 원본이며,
**현행 enum 의 원천은 코드**(`element_schema.py`·`subtypes_common.py`·`subtypes_packs.py`)다.
아래 사전에서 개명된 이름은 위 매핑표로 읽는다.

## 파이프라인 개요

```
scenario_analysis.json
   │  LLM 추출 (creative_element_analysis.json)
   ▼
vectorDB 적재 (ad_production_reference 컬렉션, record_kind 로 구분)
   ├─ record_kind="profile"   ← 영상 1개 = 1레코드 (세그먼트 검색용)
   └─ record_kind="element"   ← 크리에이티브 요소 1개 = 1레코드 (클리셰 집계용)
(전략 레퍼런스 ad_concept_reference 는 별도 파이프라인 — evaluation/concept/README.md 참고)
   ▼
검색: 카테고리/조건 → 세그먼트 n개 선정 (profile 컬렉션)
   ▼
집계: 세그먼트의 element 레코드 전체 조회
   ├─ enum 필드 빈도 집계        → 정량 클리셰 (예: 9/11 = 강한 클리셰)
   └─ description 임베딩 군집화  → enum에 없는 신규 클리셰 발견 + 고립 요소 = 클리셰 파괴
```

**클리셰 판정 기준(제안)**: 세그먼트 n개 중 빈도 ≥ 60% → 강한 클리셰, 30~60% → 관습,
1편 고립 → 클리셰 파괴 후보. `other`는 임베딩 군집화로 신규 클리셰를 발견하는 입구,
`none`은 "관습의 의도적 생략"을 집계 가능하게 만드는 장치다.

## 컬렉션 1 — `ad_production_reference`, `record_kind="profile"` (세그먼트 검색용)

추출 파일(`creative_element_analysis.json`)과 DB 레코드는 구조가 다르다.
추출 파일은 `profile`/`casting` 블록이 분리되어 있고, 적재 시(`db/chromadb/importers/production_reference.py`)
casting 이 profile 메타데이터로 평탄화되며 `summary` 는 임베딩 문서로 이동한다.

**① 추출 파일 구조** (LLM 산출물, `<data_dir>/<video_id>/creative_element_analysis.json`):

```jsonc
{
  "profile": {
    "industry_category": "beauty",             // beauty|tech_electronics|entertainment|other (v1 파일엔 없음 — 적재 시 역추정)
    "industry_secondary": null,                // optional. 복합 산업 광고(예: 다트비트=tech+entertainment)만 값 존재
    "product_category_norm": "mask",           // 산업별 enum (element_schema.py::PRODUCT_CATEGORY_NORM)
    "product_subtype": "mask_pack",            // 산업별 enum (element_schema.py::PRODUCT_SUBTYPE)
    "product_category_raw": "스킨케어 (앰플 마스크팩)",  // 원문 보존
    "target_gender": "female",                 // female|male|unisex
    "usp_category": "functional_tangible",     // concept_evaluation 과 동일 어휘 (USP_CATEGORY)
    "usp_summary": "핵심 USP 1문장",            // → DB 임베딩 문서
    "positioning_category": "by_product_innovation",  // POSITIONING_CATEGORY
    "price_tier": "premium",                   // luxury|premium|mid_range|value|unknown (가성비~럭셔리 축)
    "summary": "세그먼트 검색용 요약 3~4문장",   // → DB 임베딩 문서
    "duration_sec": 15.0,                      // 코드 계산 주입 (compute_duration)
    "duration_bucket": "15s"                   // 15s|30s|60s|other (±2s 흡수)
  },
  "casting": {                                 // beauty 외 산업은 skin_look/hair 없음
    "main_model": "solo_female", "age_band": "20s",
    "skin_look": "pale", "hair": "wet", "wardrobe": "other",
    "expression_restraint": true, "secondary_roles": "조연 서술"
  },
  "elements": [ /* 컬렉션 2 참조 */ ],
  "_meta": { "video_id": "20", "llm_backend": "claude" }
}
```

**② DB 레코드 메타데이터** (적재 시 조립, exact 필터용):

```jsonc
{
  "video_id": 20,
  "record_kind": "profile",  // "element" 과 한 컬렉션을 공유하므로 조회 시 항상 이 값으로 좁힌다
  // 세그먼트 필터 키 — profile 블록에서 복사
  "industry_category": "beauty", "product_category_norm": "mask", "product_subtype": "mask_pack",
  "product_category_raw": "스킨케어 (앰플 마스크팩)", "target_gender": "female",
  "duration_sec": 15.0, "duration_bucket": "15s",
  "usp_category": "functional_tangible", "positioning_category": "by_product_innovation",
  "price_tier": "premium", "execution_style": "slice_of_life",  // concept_evaluation 과 동일 어휘
  // 캐스팅 속성 — casting 블록에서 평탄화
  "main_model": "solo_female", "age_band": "20s", "skin_look": "pale",
  "hair": "wet", "wardrobe": "other", "expression_restraint": true,
  // elements 의 narrative_pattern 요소에서 주입
  "narrative_pattern": "emotional_journey"
}
```

임베딩 문서: `product_category_raw` + `summary` + `usp_summary` 결합.

usp/positioning 미기재 구버전 파일은 적재 시 같은 폴더의 `concept_evaluation.json` 대표값으로
백필된다 (`run.py::_enrich_from_concept`). `price_tier` 는 백필 불가 — 재추출 시에만 채워진다.

**③ 제안했으나 미구현인 필드 (향후 확장)**: `brand_name`·`placement`·`campaign_objective`·
`target_age_min/max` 는 `video_category` 컬렉션에 이미 있어 video_id 조인으로 대체
(profile 은 scenario_analysis 단독 입력 원칙). `appeal_type_primary` 등 나머지 concept_evaluation
대표값 복제와 `creative_dedup_key`(동일 소재 지면 변형 중복 제거)는 필요 시 적재 로직에 추가한다.

## 컬렉션 2 — `ad_production_reference`, `record_kind="element"` (클리셰 집계용)

**요소 1개 = 레코드 1개.**

```jsonc
{
  // ─ 식별/필터 (메타데이터) ─
  "video_id": 480,
  "record_kind": "element",
  "element_type": "sensory_demo_shot",  // 13종 enum (v2)
  "element_subtype": "cream_swirl",     // 공용+산업 팩 병합 enum
  "cut_refs": "6",                      // 근거 컷 번호 (쉼표 결합 문자열로 저장)
  // + profile 의 세그먼트 필터 키 복제 (industry_category, product_category_norm, duration_bucket ...)

  // ─ 임베딩 문서 (군집화·유사도용) ─
  "description": "금색 용기 내부 크림이 소용돌이치며 솟아오르는 매크로 샷",
  "production_detail": "컷6에서 매크로 렌즈로 크림 질감 클로즈업, 시각적 임팩트 극대화"
}
```

---

# enum 사전 — element_type 13종 + subtype 정의

## 1. opening_hook — 오프닝 훅

**정의**: 영상 첫 1~3초에 시청자 이탈을 막기 위해 배치되는 도입 연출. 광고에서 가장 정형화되기
쉬운 구간으로, 세그먼트 내 오프닝 유형의 수렴도가 클리셰 강도를 가장 직관적으로 보여준다. 영상당 1개.

| subtype | 설명 |
|---|---|
| product_static | 무지 배경(암전·화이트 등) 중앙에 제품을 정면 고정 배치하고 조명·텍스트로 시작. 브랜드를 즉시 각인시키는 가장 보수적인 오프닝 |
| object_macro | 제품 대신 상징 오브제(원료 식물, 장식함, 보석 등)의 매크로 클로즈업으로 시작. 세계관·프리미엄 무드를 먼저 구축 |
| face_closeup_dark | 어두운 화면에서 인물 얼굴이 서서히 드러나거나 눈을 뜨는 클로즈업. 몰입·긴장감으로 후킹 |
| face_closeup_backlight | 역광·확산광이 감싸는 얼굴 클로즈업으로 시작. 피부 광채와 감성 무드를 동시에 제시 |
| silhouette_backlight | 강한 역광으로 인물을 검은 실루엣 처리(얼굴 미노출)해 신비감·호기심 유발 |
| question_copy | 시청자에게 던지는 질문형 카피·대사로 시작. 공감 유발 후 본문에서 답을 제시하는 구조의 진입점 |
| problem_statement | 불편·고민 상황을 서술하는 내레이션/장면으로 시작하는 문제 제기형 오프닝 |
| action_dynamic | 빠른 움직임·스포츠·파도 등 동적 스펙터클로 시작해 시선을 강제로 붙잡는 유형 |
| other | 위 유형에 속하지 않는 오프닝 (자유 서술로 기록) |

## 2. model_direction — 인물 연출

**정의**: 모델의 캐스팅 조건과 표정·시선 연출. 뷰티 광고에서 "누구를, 어떤 표정으로 찍는가"는
제품 컷보다 강하게 관습화되어 있어 캐스팅 속성(다중)과 표정 아크(영상당 1개)를 분리해 기록한다.

### 캐스팅 속성 (boolean/enum, 다중)

| 속성 | 설명 |
|---|---|
| solo_female / solo_male / couple / group | 메인 모델 구성. 권위 장치로 등장하는 조연(의료인·연구원 등)은 별도 `secondary_roles`에 기록 |
| age_band | 메인 모델의 연출상 연령대 (teens / 20s / 30s / 40s+ / variable). variable은 연령 변화를 서사 장치로 쓰는 경우 |
| skin_look | 피부 표현 방향. clear_glow(맑고 윤기), matte(보송), pale(창백·시네마틱), textured(모공·결 사실 묘사) |
| hair | 헤어 연출. long_straight(긴 생머리), wet(젖은 머리), tied_back(묶음/정돈), short, styled(웨이브 등) |
| wardrobe | 의상 코드. off_shoulder/sleeveless(목·어깨 라인 노출로 피부 면적 확보), dress, casual, uniform |
| expression_restraint | 절제된 표정 기조 여부. 무표정~차분을 유지하며 감정 연기를 배제하는 뷰티 관습의 핵심 지표 |

### 표정 아크 subtype (영상당 1개)

| subtype | 설명 |
|---|---|
| neutral_to_smile | 무표정·불편한 표정에서 미소로 전환. '사용 후 만족'을 표정 변화로 증명하는 비포-애프터의 인물 버전 |
| neutral_to_gaze | 시선 회피·고개 숙임에서 카메라 정면 응시로 전환. '자신감 회복' 서사를 시선으로 표현 |
| eyes_closed_to_open | 눈 감은 상태에서 눈을 뜨며 응시. '각성·깨어남'을 제품 효능의 은유로 사용 |
| deadpan_hold | 무표정을 끝까지 유지. 감정 대신 피부·제품에 시선을 고정시키는 절제형 (럭셔리·클리니컬 톤에서 빈발) |
| smile_repeat | 미소·만족 표정을 여러 컷에서 반복. 친근함·긍정 정서 중심의 대중 브랜드형 |
| silhouette_to_gaze | 실루엣·미노출 상태에서 점진적으로 얼굴을 공개. 신비감을 리빌로 해소하는 구조 |
| emotional_range | 불안·긴장 등 부정 정서를 포함한 넓은 감정 연기. 스토리텔링형 광고에서 사용 |
| other | 위에 속하지 않는 아크 |

## 3. texture_shot — 제형/질감 샷

**정의**: 제품의 제형(크림·액체·젤)이나 효능을 시각화하는 매크로·CG 샷. 뷰티 광고의
"제품이 좋아 보이게 하는" 핵심 관습 구간이며, 단일 샷 수준에서 클리셰가 가장 명확하게 반복된다.
영상당 다중.

| subtype | 설명 |
|---|---|
| cream_swirl | 용기·그릇 속 크림이 소용돌이/회오리 형태로 연출된 매크로 샷. 풍부한 제형감의 정형 기호 |
| liquid_macro | 액체·에센스·오일의 극단적 매크로 (점도, 반사광, 얕은 심도). 성분의 농축감 표현 |
| bubble_macro | 투명 액체 속 기포·산란광 매크로. '깨끗한 성분' 이미지의 추상화 |
| droplet_on_skin | 촉촉한 피부 위 물방울·에센스가 맺히거나 흐르는 클로즈업. 보습감의 촉각적 표현 |
| application_closeup | 손가락 도포, 펌프·스포이드 사용 등 실사용 동작의 초근접 샷. 발림성·흡수감 전달 |
| cg_particle | 효능 메커니즘을 추상 CG로 은유 (입자·구체·네트워크·터널 등). 눈에 안 보이는 작용의 시각화 |
| skin_graphic_overlay | 실제 얼굴 위에 성분 작용·피부 조직 그래픽을 합성. 효능 설명과 인물 샷의 결합형 |
| none | 제형/질감 샷이 없는 경우도 명시적으로 기록 (그래픽·서사로 대체하는 변주 감지용) |

## 4. trust_device — 신뢰 장치

**정의**: 효능 주장을 뒷받침하기 위해 동원되는 근거·권위 연출. rational_info 소구의 실행 수단이며,
세그먼트 내 "어떤 종류의 근거가 관습인가"를 보여준다. 영상당 다중.

| subtype | 설명 |
|---|---|
| clinical_spec_number | 임상·시험 수치, 스펙 수치 자막 (개선율 %, 지속 시간, 성분 개수 등) |
| sales_market_number | 판매량·재구매율·시장 순위 등 상업적 실적 수치 (제3자 조사기관 출처 병기 포함) |
| heritage_number | 업력·창립연도·연구 기간 등 시간 기반 권위 숫자 |
| authority_figure | 의료인·연구원·전문가의 등장(실사·합성 불문)으로 전문성을 인격화 |
| certification_note | 기능성 인증·시험 조건·법적 고지 문구를 화면 하단 등에 노출 |
| ingredient_claim | 독자 성분명·원료 스토리를 자막/내레이션으로 강조 (수치 없이 성분 자체가 근거) |
| split_comparison | 화면 분할·'VS' 구도로 경쟁 대안(시술, 타사, 사용 전)과 직접 비교 |
| before_after_demo | 사용 전후 변화를 한 화면/연속 컷에서 시연 (글자 소멸, 피부 변화 등) |
| testimonial | 실사용자 후기·별점·리뷰 인용 |
| award_badge | 수상·랭킹 뱃지 그래픽 노출 |
| none | 신뢰 장치가 전무한 경우 명시 기록 (무드·세계관만으로 설득하는 변주 감지용) |

## 5. product_shot — 제품 컷

**정의**: 제품 패키지를 보여주는 샷의 연출 방식과 엔딩 처리. 오프닝과 함께 가장 정형화된 구간으로,
"제품을 어디에 어떻게 모셔두는가"의 관습을 기록한다. 영상당 다중.

| subtype | 설명 |
|---|---|
| center_package | 미니멀/어두운 배경 중앙에 제품 단독 배치 + 조명 강조. 푸시인·발광 결합이 전형 |
| levitation | 제품이 공중에 떠오르거나 떠 있는 연출. 신성함·특별함의 기호 (제단·수중·무중력 등 배경 불문) |
| rotation_reveal | 오비탈·턴테이블 회전, 크레인 무빙으로 제품을 다각도 리빌 |
| mass_array | 동일 제품 다수를 반복 배열해 물량감·판매량·라인업을 시각화 |
| open_texture_reveal | 뚜껑이 열리며 내용물·내부 조명이 드러나는 연출 |
| model_holding | 모델이 제품을 손에 들거나 사용하는 상태로 제품 강조 (초점 이동 포함) |
| model_ending | 엔딩을 제품이 아닌 모델(+로고)로 마무리 |
| logo_only_endcard | 제품 없이 로고·슬로건·사명만 남기는 미니멀 엔드카드 |
| other | 위에 속하지 않는 제품 연출 |

## 6. color_light_code — 색·조명 코드

**정의**: 영상 전반의 팔레트, 조명 기법, 톤 전환 설계. '프리미엄', '임상', '변화' 같은 추상 가치를
색과 빛으로 기호화하는 방식을 기록한다. 영상당 다중.

| subtype | 설명 |
|---|---|
| gold_luxury | 금색·황금빛·로즈골드 팔레트로 프리미엄·럭셔리를 기호화 |
| dark_background | 어두운 배경 위 피사체만 발광시키는 대비 구도 (럭셔리·클리니컬 겸용) |
| bright_minimal | 밝은 화이트·베이지 미니멀 공간 기조 (청결·데일리 무드) |
| dark_to_bright | 어둠→밝음 톤 전환으로 문제→해결·변화 서사를 형식에 내장 |
| backlight_flare | 역광·렌즈 플레어·과노출 전환으로 피부와 인물을 신성화 |
| brand_colorblock | 브랜드 컬러 1~2색의 단색 블록으로 화면을 통일 (컬러 아이덴티티 각인) |
| cool_mono | 블루·청록 등 한랭 모노톤 통일 (뷰티 관습인 웜톤의 역방향) |
| warm_natural | 자연광·웜톤의 일상적 라이팅 (slice_of_life 계열) |
| other | 위에 속하지 않는 색·조명 설계 |

## 7. copy_device — 카피 장치

**정의**: 카피·자막·내레이션의 수사 기법과 텍스트 연출. 클리셰 분석에서 차별화 시도가 가장 자주
일어나는 층위이므로, 상투구와 언어유희를 같은 축에서 대조할 수 있게 기록한다. 영상당 다중.

| subtype | 설명 |
|---|---|
| transformation_phrase | "다시 태어나다·되돌리다·바꾸다"류 재생·회복 상투구 |
| time_motif | '시간'을 철학적 모티프로 쓰는 카피 (안티에이징 전용 상투구) |
| essence_motif | "피부 본연·근본·자생력"류 본질 회귀 상투구 |
| spec_listing | 수치·성분·인증을 나열하는 정보형 카피 (숫자 빌드업 포함) |
| double_coding | 내레이션과 자막으로 동일 문구를 이중 전달해 각인 |
| wordplay | 중의어·동음이의·개사 등 언어유희 |
| archaic_tone | 고어체·경전체 등 특수 어투 채택 |
| question_answer | 질문 제기→반박/답변의 문답 구성 |
| declaration | 브랜드 선언문형 카피 ("~하다"로 끝나는 단정형 슬로건) |
| keyword_isolation | 핵심 단어만 색·크기로 분리 강조하는 타이포 연출 |
| typo_object | 대형 3D 타이포를 오브제로 쓰는 그래픽 연출 |
| other | 위에 속하지 않는 카피 장치 |

## 8. narrative_pattern — 서사 구조

**정의**: 영상 전체의 이야기 골격과 컷 역할 배열. 기존 `narrative_structure` 필드를 계승하되
클리셰 분석용으로 세분화한다. 영상당 1개 + role_sequence 문자열 병기.

| subtype | 설명 |
|---|---|
| hook_body_close | 훅→본문(효능·무드 전개)→브랜드 클로즈. 15초 광고의 기본 골격 |
| problem_solution | 문제·고민 환기→제품 등장→해결. agitation(불안 증폭) 강조형 포함 |
| before_after_bridge | 사용 전후 상태 대비를 다리로 잇는 구성 (인물 표정·피부·톤 변화로 표현) |
| qna_argument | 질문 제기→반박→근거 제시의 논증형 구성 |
| informational_demo | 선언→시연→신뢰 마무리의 정보 전달형 (서사보다 데모 중심) |
| emotional_journey | 감정·무드의 여정으로 전개, 제품은 후반 등장 (시네마틱형) |
| comparison_verdict | 비교 대상과의 대결 구도로 전개해 우위 판정으로 마무리 |
| other | 위에 속하지 않는 구조 |

## 9. sound_pattern — 사운드 설계

**정의**: BGM 장르 운용과 SFX 배치 방식. 편집 리듬의 관습을 기록하는 축. 영상당 다중.
(분석 파이프라인의 음악 기술 어휘가 제한적일 수 있어, 판정 시 다른 축보다 보수적으로 해석할 것.)

| subtype | 설명 |
|---|---|
| sfx_cut_sync | 드럼히트·신스스탭·쉐이커 등 SFX를 컷 전환·자막 등장 타이밍에 동기화 |
| genre_shift_per_cut | 컷/구간마다 BGM 장르·무드를 전환해 감정 곡선을 설계 |
| bgm_mute_transition | 클라이맥스 직전 배경음을 소거했다가 재고조시키는 대비 연출 |
| crescendo_build | 단일 곡을 점진 고조시켜 엔딩 임팩트로 연결 |
| narration_led | 내레이션이 주도하고 음악은 배경으로 절제 |
| jingle_signature | 브랜드 고유 징글·시그니처 사운드 사용 |
| other | 위에 속하지 않는 사운드 설계 |

## 10. persuasion_engine — 설득 엔진

**정의**: `generation/v5_m0_m3/prompts/module5.md` L2 와 동일 어휘. 영상이 무엇을 "논증"하는가
(narrative_pattern 의 구조 골격과는 다른 축). M5 가 `recentengines`(세그먼트 내 최근 확정 엔진)를
입력받아 반-수렴하므로, 완성 광고를 이 어휘로 역분류해두면 M5 가 "이미 많이 쓰인 엔진"을
검색으로 확인할 수 있다. 영상당 1개.

| subtype | 설명 |
|---|---|
| pas | Problem-Agitate-Solution — 문제 환기 후 해결. 비포애프터형 남용 1순위 |
| aida | Attention-Interest-Desire-Action — 신카테고리·문제 미인식 오디언스용 |
| bab | Before-After-Bridge — 변환 약속형. PAS 와 함께 반-수렴 대상 1순위 |
| product_demo | 제품 시연 중심 — 평가 단계 오디언스, 재수렴 2순위로 흔함 |
| star_story_solution | 증언·변환 서사 — 정체성 소구 |
| four_ps | Promise-Picture-Proof-Push — 문제 프레임 없이 약속→그림→증거→푸시 |
| social_proof | 사회적 증거(후기·판매량·순위) 중심 |
| unique_mechanism | 고유 메커니즘·원리 제시로 차별화 |
| fab | Feature-Advantage-Benefit — 속성→이점→혜택 순 서술 |
| none | 특정 설득 엔진 미사용(엔진 미장착 근거가 있는 경우만) |

## 11. narrative_form — 서사 형식

**정의**: module5.md L2.5 와 동일 어휘. 어떤 이야기 "형식"으로 전달하는가(설득 논리와 분리된
축). "선형 미니드라마" 디폴트 수렴을 막기 위한 형식 메뉴 12종. 영상당 1개.

| subtype | 설명 |
|---|---|
| linear_mini_drama | 선형 미니드라마 — 카테고리 디폴트, 반-수렴 대상 1순위 |
| vignette_anthology | 비네트·앤솔로지 — 주인공 없는 3~4개 미니씬 나열 |
| contrast_parallel | 대조·평행 — A vs B, with·without 구도 |
| enumeration | 열거 — rapid-fire 리스트 나열 |
| twist | 반전 — turn 지점에서 기대 전복 |
| oneshot_longtake | 원샷·롱테이크 |
| pov_first_person | POV·1인칭 시점 |
| mockumentary_vox_pop | 모큐멘터리·인터뷰·vox-pop |
| metaphor_world | 은유세계 — 제품 세계를 장소로 구현 |
| demo_spectacle | 데모-스펙터클 — ASMR·공정 시각화·oddly satisfying |
| absurd_exaggeration | 부조리 과장 |
| everyday_montage | 일상 몽타주 — 중심 갈등 없는 나열형 |

## 12. tone_register — 톤 레지스터 역전

**정의**: module5.md L2.6 과 동일 개념. 카테고리 디폴트 톤(예: 건강식품=따뜻·걱정) 대비 실제
반전 여부·방향. 고정 enum 이 아니라 module5.md 가 예시로 든 반전 패턴을 닫힌 집합으로 삼는다
(자유서술로 두면 영상마다 라벨이 갈려 빈도 집계가 무의미해진다). 영상당 1개.

| subtype | 설명 |
|---|---|
| heavy_to_comedy | 무거움→코미디 반전 |
| serious_to_deadpan | 진지→데드팬 반전 |
| loud_to_flex | 시끄러움→자랑(플렉스) 반전 |
| sales_to_documentary | 파는 톤→다큐 반전 |
| category_default | 카테고리 디폴트 톤 유지(반전 없음) |
| other | 위 패턴에 속하지 않는 반전 |

---

## 부록 — 스킨케어 15초 세그먼트 (n=11) 검증 결과 요약

video_id: 343, 348, 325, 480, 332, 346, 345, 504, 344, 20, 335 (2026-07 수동 분석)

| 요소 | 빈도 | 판정 |
|---|---|---|
| sound: sfx_cut_sync | 11/11 | 강한 클리셰 |
| product_shot: 중앙 배치 + 로고 엔드카드 | 11/11 | 강한 클리셰 |
| casting: 여성 단독·20~30대·맑은 피부·긴 생머리 | 8~11/11 | 강한 클리셰 |
| texture: 제형/입자 매크로 (전 유형 합산) | 10/11 | 강한 클리셰 |
| casting: expression_restraint | 8/11 | 강한 클리셰 |
| trust_device 1개 이상 보유 | 9/11 | 강한 클리셰 |
| opening: 제품 정면 or 어둠 속 얼굴 | 9/11 | 강한 클리셰 |
| color: gold_luxury | 4/11 | 관습 |
| product_shot: levitation | 4/11 | 관습 |
| texture: cream_swirl | 3/11 | 관습 |
| copy: transformation/time 상투구 | 5/11 | 관습 |
| wordplay·archaic·qna, 거꾸로 얼굴 오프닝, cool_mono, pale skin | 각 1~3/11 | 클리셰 파괴 요소 |
