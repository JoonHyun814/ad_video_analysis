# 분석 모델 스키마 문서


## 1. 서사 판별 (`narrative_classification`)

광고가 스토리 구조를 가지는지 여부를 판별한다.

| 필드 | 타입 | 의미 |
|------|------|------|
| `narrative_type` | string (enum) | 서사 유형 |
| `confidence` | float (0.0~1.0) | 판별 확신도. 1.0에 가까울수록 명확한 판별 |
| `reasoning` | string | 판별 근거 (자유 텍스트) |

### narrative_type 값

| 값 | 의미 |
|----|------|
| `NARRATIVE` | 인물·갈등·해결 등 스토리 흐름이 있는 광고 |
| `NON_NARRATIVE` | 제품 쇼케이스·이미지 나열 등 서사 없는 광고 |

> `narrative_type`, `confidence`는 최상위로도 복사된다 (`_inject_meta`).

---

## 2. 전체 전략 (`overall_strategy`)

광고의 크리에이티브 전략을 구조·훅·사운드·엔딩·메시지 5개 축으로 분해한다.

---

### 2.1 서사 구조

| 필드 | 타입 | 의미 |
|------|------|------|
| `narrative_structure` | string (enum) | 광고 전체의 스토리 구조 패턴 |
| `creative_style` | string (enum) | 크리에이티브 표현 방식 |
| `tagline` | string \| null | 광고에 등장하는 슬로건·태그라인. 없으면 null |

#### narrative_structure 값

| 값 | 의미 |
|----|------|
| `problem_agitation_solution` | 문제 제시 → 감정 자극 → 해결책 순의 3단 구조 |
| `before_after_bridge` | 사용 전 상태 → 제품 경험 → 사용 후 변화 |
| `testimonial_arc` | 실사용자·전문가 증언을 축으로 전개 |
| `hook_body_close` | 주의 집중 → 핵심 내용 → 마무리 CTA의 범용 구조 |
| `functional_appeal` | 기능·스펙 중심의 정보 전달형 |
| `non_narrative` | 서사 구조 없음 (이미지·제품 나열) |

#### creative_style 값

| 값 | 의미 |
|----|------|
| `problem_solution` | 문제-해결 대비를 핵심 메시지로 활용 |
| `emotional_story` | 감성·공감을 자극하는 스토리 중심 |
| `product_showcase` | 제품 외관·기능을 직접적으로 부각 |
| `testimonial` | 실사용자 또는 전문가 추천 방식 |
| `comparison` | 경쟁 제품 또는 사용 전후 비교 |
| `humor` | 유머·웃음 코드로 브랜드 친근감 형성 |
| `educational` | 정보·지식 제공 중심 |
| `lifestyle` | 브랜드가 지향하는 삶의 방식 표현 |
| `event_promo` | 한정 이벤트·프로모션 강조 |
| `brand_film` | 브랜드 세계관·철학을 영화적으로 표현 |
| `ugc_style` | 사용자 제작 콘텐츠처럼 자연스러운 연출 |
| `emotional_appeal` | 감정적 공명을 직접 자극 |
| `storytelling` | 서사·캐릭터 중심의 미니 드라마 형식 |

---

### 2.2 훅 전략 (`hook_strategy`)

광고 초반 시청자를 붙잡는 방식을 분석한다. 스킵 저항과 직결된다.

| 필드 | 타입 | 의미 |
|------|------|------|
| `technique` | string (enum) | 첫 3초에서 사용한 주의 집중 기법 |
| `skip_resistance_strategy` | string (enum) | 스킵 버튼을 누르지 않게 만드는 전략 |
| `opening_device` | string | 오프닝 장치 서술 (자유 텍스트) |
| `first_frame_element` | string | 첫 프레임에 등장하는 핵심 시각 요소 서술 |
| `speech_in_first_scene` | bool | 첫 씬에 보이스·대사가 있는지 여부 |
| `text_in_first_scene` | bool | 첫 씬에 자막·텍스트가 있는지 여부 |
| `brand_in_first_scene` | bool | 첫 씬에 브랜드·로고가 노출되는지 여부 |

#### technique (훅 기법) 값

| 값 | 의미 |
|----|------|
| `question` | "이거 알고 계셨나요?" 형태의 질문으로 호기심 유발 |
| `shock` | 예상 밖의 충격적 장면·발언으로 시선 고정 |
| `empathy` | 공감되는 상황·감정으로 시청자를 끌어들임 |
| `visual_impact` | 강렬한 색감·움직임·구도로 시각적 임팩트 |
| `statement` | 강한 주장·선언문으로 신뢰·흥미 유발 |
| `story` | 서사의 한복판에서 시작해 궁금증 유도 |
| `no_hook` | 명확한 훅 장치 없음 |
| `direct_benefit` | 혜택을 즉시 제시해 이탈 방지 |
| `celebrity_appearance` | 유명인 등장으로 주목도 확보 |
| `visual_surprise` | 예상치 못한 비주얼 전환으로 시선 고정 |
| `social_proof_opening` | 리뷰 수·사용자 수 등 사회적 증거를 오프닝에 배치 |
| `problem_dramatization` | 문제 상황을 과장·극적으로 연출 |

#### skip_resistance_strategy 값

| 값 | 의미 |
|----|------|
| `curiosity_gap` | 정보 공백을 만들어 끝까지 보게 만듦 |
| `immediate_value` | 즉각적인 혜택·정보를 초반에 제시 |
| `emotional_hook` | 감정 몰입으로 이탈 욕구 억제 |
| `pattern_interrupt` | 익숙한 광고 공식을 깨는 연출로 주의 유지 |
| `social_proof` | 타인의 검증·경험을 보여줘 신뢰 형성 |
| `fear_of_missing` | 놓치면 손해라는 FOMO 심리 자극 |

---

### 2.3 오디오·비주얼 전략 (`audio_visual_strategy`)

음성·음악·텍스트의 역할 분담을 분석한다. 음소거 시청 환경에서의 메시지 전달력과 직결된다.

| 필드 | 타입 | 의미 |
|------|------|------|
| `voiceover_type` | string (enum) | 내레이션·보이스오버의 화자 유형 |
| `voiceover_tone` | string (enum) | 보이스오버의 감정·어조 |
| `music_role` | string (enum) | 배경음악이 광고에서 수행하는 역할 |
| `music_tempo` | string (enum) | 배경음악의 템포 |
| `text_carries_primary_message` | bool | 자막·텍스트가 핵심 메시지를 주도하는지 여부. `true`면 음소거 시청에도 메시지 전달 가능 |

#### voiceover_type 값

| 값 | 의미 |
|----|------|
| `narrator` | 익명 나레이터. 객관적·설명적 어조 |
| `character` | 광고 속 등장인물이 직접 말함 |
| `character_voice` | 브랜드 마스코트·캐릭터의 목소리 |
| `none` | 보이스오버 없음 |

#### voiceover_tone 값

| 값 | 의미 |
|----|------|
| `conversational` | 일상 대화처럼 친근한 어조 |
| `authoritative` | 전문가·권위자처럼 신뢰감 있는 어조 |
| `warm` | 따뜻하고 감성적인 어조 |
| `energetic` | 활기차고 열정적인 어조 |
| `playful` | 유쾌하고 장난기 있는 어조 |
| `informative` | 정보 전달 중심의 건조한 어조 |
| `comedic` | 웃음을 유도하는 코미디 어조 |

#### music_role 값

| 값 | 의미 |
|----|------|
| `background_mood` | 분위기 조성 역할. 메시지를 주도하지 않음 |
| `narrative_driver` | 음악의 전개가 광고 서사를 이끎 |
| `rhythm_driver` | 컷 편집·화면 전환이 음악 리듬에 맞춰짐 |
| `emotional_peak` | 감정 클라이맥스 장면에서 음악이 폭발적으로 강조됨 |
| `brand_signature` | 브랜드 고유의 징글·사운드로 브랜드 인식 강화 |
| `none` | 음악 없음 |

#### music_tempo 값

| 값 | 의미 |
|----|------|
| `slow` | 느린 템포. 감성·명상적 분위기 |
| `moderate` | 보통 템포. 정보 전달에 적합 |
| `fast` | 빠른 템포. 역동적·스포티한 분위기 |
| `upbeat` | 밝고 경쾌한 템포. 긍정적 감정 유도 |
| `variable` | 템포가 장면에 따라 가변적 |
| `none` | 음악 없음 |

---

### 2.4 클로즈 전략 (`close_strategy`)

광고 마지막 구간(엔딩)의 브랜딩 방식과 행동 유도 장치를 분석한다.

| 필드 | 타입 | 의미 |
|------|------|------|
| `close_type` | string (enum) | 엔딩의 주된 목적·연출 방식 |
| `end_card_elements` | string[] (enum) | 엔드카드에 등장하는 요소 목록 (복수 선택) |
| `cta_type` | string (enum) \| null | 행동 유도 장치의 유형. 없으면 null |
| `promo_info` | string \| null | 할인·이벤트 등 프로모 정보 서술. 없으면 null |

#### close_type 값

| 값 | 의미 |
|----|------|
| `brand_emotion` | 브랜드 감성·세계관을 각인시키는 엔딩 |
| `conversion_heavy` | 구매·가입 등 즉각 전환을 강하게 유도 |
| `promo_driven` | 할인·기간 한정 이벤트를 전면에 내세움 |
| `product_showcase` | 제품 패키지·외관을 클로즈업으로 마무리 |
| `app_download` | 앱스토어 배지와 QR 코드로 앱 설치 유도 |
| `minimal_logo` | 로고만 노출하는 간결한 브랜드 마무리 |

#### end_card_elements 값

| 값 | 의미 |
|----|------|
| `logo` | 브랜드 로고 |
| `cta_text` | "지금 구매", "무료 체험" 등 CTA 문구 |
| `app_badge` | App Store / Google Play 배지 |
| `tagline` | 브랜드 슬로건 |
| `promo_text` | 할인율·기간 등 프로모션 문구 |
| `qr_code` | QR 코드 |
| `product_image` | 제품 이미지 |

#### cta_type 값

| 값 | 의미 |
|----|------|
| `app_download_badge` | 앱스토어 배지를 통한 앱 설치 유도 |
| `qr_code` | QR 코드 스캔을 통한 랜딩 |
| `url_visit` | URL 방문 안내 |
| `phone_call` | 전화 걸기 유도 |
| `store_visit` | 매장 방문 유도 |
| `custom` | 위 유형에 해당하지 않는 커스텀 CTA |

---

### 2.5 메시지 위계 (`message_hierarchy`)

광고가 전달하는 메시지의 우선순위와 반복도를 분석한다.

| 필드 | 타입 | 의미 |
|------|------|------|
| `primary_message` | string | 광고 전체를 관통하는 단 하나의 핵심 메시지 |
| `supporting_messages` | string[] | 핵심 메시지를 보완하는 부가 메시지 목록 |
| `message_repetition_count` | int | 핵심 메시지가 반복되는 횟수. 높을수록 단순·직접적 전략 |

---

## 3. 시퀀스 (`sequences`)

컷들을 `hook → body → close` 3단계로 묶은 시간 구간 단위. 3~5개 생성된다.

| 필드 | 타입 | 의미 |
|------|------|------|
| `sequence_id` | int | 시퀀스 순번 (1부터) |
| `sequence_label` | string (enum) | 시퀀스가 속하는 광고 단계 |
| `start_sec` | float | 시작 시간 (초) |
| `end_sec` | float | 종료 시간 (초) |
| `intent` | string (enum) | 이 시퀀스가 시청자에게 의도하는 반응 |
| `num_cuts` | int | 이 시퀀스에 포함된 컷 수 |
| `delivery` | string (enum) | 메시지 전달 수단 |
| `brand_visible` | bool | 이 시퀀스 구간에 브랜드가 보이는지 여부 |
| `product_visible` | bool | 이 시퀀스 구간에 제품이 보이는지 여부 |

### sequence_label 값

| 값 | 의미 |
|----|------|
| `hook` | 도입부. 시청자 주의를 끄는 구간 |
| `body` | 전개부. 메시지·제품·기능을 전달하는 구간 |
| `close` | 마무리부. 브랜딩과 CTA가 집중되는 구간 |

### intent 값

| 값 | 의미 |
|----|------|
| `provoke_curiosity` | 호기심을 자극해 시청을 이어가게 함 |
| `create_urgency` | "지금 해야 한다"는 긴급성 전달 |
| `build_trust` | 신뢰·공신력 형성 |
| `demonstrate_value` | 제품·서비스의 가치를 직접 시연 |
| `evoke_aspiration` | 더 나은 삶·자아에 대한 열망 자극 |
| `deliver_information` | 사실·수치·기능 정보 전달 |
| `drive_action` | 구매·설치·방문 등 즉각 행동 유도 |
| `reinforce_brand` | 브랜드 이미지·정체성 각인 |

### delivery 값

| 값 | 의미 |
|----|------|
| `voice_only` | 음성(나레이션·대사)만으로 전달. 음소거 시 메시지 손실 |
| `text_only` | 자막·텍스트만으로 전달. 음소거에 최적화 |
| `voice_and_text` | 음성과 자막을 동시 사용. 가장 높은 전달력 |
| `visual_only` | 시각 연출만으로 전달. 언어 장벽 없음 |

---

## 4. 컷 (`cuts`)

씬 전환(컷 편집) 기준으로 분할된 최소 단위. `cut_id`는 `scenario_analysis`의 `cut_index`와 동일하다.

| 필드 | 타입 | 의미 |
|------|------|------|
| `cut_id` | int | 컷 번호 (영상 전체 기준 1부터, `cut_index`와 일치) |
| `sequence_id` | int | 이 컷이 속하는 시퀀스의 `sequence_id` |
| `start_sec` | float | 시작 시간 (초) |
| `end_sec` | float | 종료 시간 (초) |
| `role` | string (enum) | 이 컷이 서사에서 수행하는 역할 |
| `plot` | string | 이 컷의 화면 내용 묘사 (자유 텍스트) |
| `narration` | string \| null | 이 컷의 나레이션·대사. 없으면 null |
| `text` | string \| null | 이 컷에 표시된 화면 텍스트·자막. 없으면 null |
| `brand_visible` | bool | 이 컷에 브랜드·로고가 보이는지 여부 |
| `product_visible` | bool | 이 컷에 제품이 보이는지 여부 |
| `brand_assets` | string[] (enum) | 이 컷에 등장하는 브랜드 자산 목록 |

### role (서사 역할) 값

| 값 | 의미 |
|----|------|
| `HOOK` | 시청자 주의를 끄는 첫 장면 |
| `ESTABLISH_CONTEXT` | 상황·배경·등장인물을 소개하는 장면 |
| `PROBLEM` | 해결이 필요한 문제나 불편함을 제시하는 장면 |
| `SOLUTION` | 제품·서비스가 문제를 해결하는 장면 |
| `FEATURE` | 제품의 기능·특장점을 직접 보여주는 장면 |
| `PROOF` | 리뷰·수치·인증 등 신뢰 근거를 제시하는 장면 |
| `EXPERIENCE` | 실제 사용 경험을 묘사하는 장면 |
| `OUTCOME` | 사용 후 달라진 결과·변화를 보여주는 장면 |
| `PROMO` | 할인·기간 한정 이벤트를 강조하는 장면 |
| `CTA` | 구매·설치·방문 등 행동을 유도하는 장면 |
| `EMOTIONAL_APPEAL` | 감정·공감으로 시청자와 연결되는 장면 |
| `VISUAL_FILLER` | 메시지 없이 시각적 전환·리듬 조절용 장면 |
| `BRAND` | 로고·슬로건으로 브랜드를 각인시키는 마무리 장면 |

### brand_assets 값

| 값 | 의미 |
|----|------|
| `product` | 제품 실물 |
| `logo` | 브랜드 로고 |
| `app_ui` | 앱 화면·UI |
| `brand_icon` | 브랜드 전용 아이콘 |
| `brand_character` | 브랜드 마스코트·캐릭터 |
| `packaging` | 제품 패키지·포장 |

---

## 5. 핵심 장면 (`key_scenes`)

광고 전체에서 2~4개의 대표 장면을 선정한다. 썸네일·하이라이트 용도로 활용된다.

| 필드 | 타입 | 의미 |
|------|------|------|
| `start_sec` | float | 장면 시작 시간 (초) |
| `end_sec` | float | 장면 종료 시간 (초) |
| `location` | string (enum) | 촬영 장소 유형 |
| `subject` | string (enum) | 화면 주체 |
| `key_scene_describe` | string | 장면을 한 문장으로 묘사 |

### location 값

| 값 | 의미 |
|----|------|
| `indoor` | 실내 (가정·매장·오피스 등) |
| `outdoor` | 실외 (거리·자연 등) |
| `studio` | 스튜디오 배경 |
| `cgi` | 3D·CG 합성 화면 |
| `mixed` | 실사와 CG를 혼합한 화면 |

### subject 값

| 값 | 의미 |
|----|------|
| `person` | 인물만 등장 |
| `product` | 제품만 등장 |
| `object` | 사물·소품이 주체 |
| `environment` | 공간·배경이 주체 |
| `person_with_product` | 인물과 제품이 함께 등장 |
| `abstract` | 추상적·개념적 비주얼 |
| `text_graphic` | 텍스트·그래픽이 주체 |

---

## 6. 캠페인 브리프 (`brief`)

광고의 마케팅 목적과 타겟을 AI가 역추론한 값이다.

| 필드 | 타입 | 의미 |
|------|------|------|
| `campaign_objective` | string (enum) | 이 광고가 달성하려는 마케팅 목표 |
| `industry_category` | string (enum) | 광고주의 산업 분류 |
| `brand_name` | string | 브랜드명 |
| `target_gender` | string (enum) | 주 타겟 성별 |
| `target_age_range` | string | 주 타겟 연령대 (예: `"25-44"`) |
| `target_interest` | string[] | 타겟의 관심사·라이프스타일 키워드 목록 |
| `placement` | string (enum) | 광고가 노출되는 미디어 포맷 |
| `key_message` | string | 광고의 핵심 메시지 한 문장 |

### campaign_objective 값

| 값 | 의미 |
|----|------|
| `awareness` | 브랜드 인지도 확산 |
| `consideration` | 구매 고려 단계 진입 유도 |
| `conversion` | 즉각 구매·가입 전환 |
| `retention` | 기존 고객 재구매·유지 |
| `app_install` | 앱 설치 유도 |
| `traffic` | 웹사이트·랜딩 페이지 방문 유도 |

### industry_category 값

| 값 | 의미 |
|----|------|
| `food_beverage` | 식품·음료 |
| `beauty_cosmetics` | 뷰티·화장품 |
| `fashion_apparel` | 패션·의류 |
| `tech_electronics` | 기술·전자기기 |
| `finance_insurance` | 금융·보험 |
| `retail_ecommerce` | 유통·이커머스 |
| `health_wellness` | 건강·웰니스 |
| `automotive` | 자동차 |
| `travel_hospitality` | 여행·숙박 |
| `education` | 교육 |
| `real_estate` | 부동산 |
| `gaming_entertainment` | 게임·엔터테인먼트 |
| `telecom` | 통신 |

### target_gender 값

| 값 | 의미 |
|----|------|
| `male` | 남성 타겟 |
| `female` | 여성 타겟 |
| `all` | 성별 구분 없음 |

### placement 값

| 값 | 의미 |
|----|------|
| `ctv_6s` | CTV 6초 (스킵 불가 형식) |
| `ctv_15s` | CTV 15초 |
| `ctv_30s` | CTV 30초 |
| `ctv_60s` | CTV 60초 (장편 브랜드 필름) |

---

## 7. 요약 필드 (최상위)

| 필드 | 타입 | 의미 |
|------|------|------|
| `role_sequence` | string | 각 컷의 `role` 값을 컷 순서대로 콤마 연결한 문자열. 광고 서사 흐름을 한눈에 파악하는 데 사용 (예: `"HOOK,ESTABLISH_CONTEXT,FEATURE,PROOF,CTA"`) |
| `narrative_summary` | string | 광고 전체 서사를 2~3문장으로 요약 |
| `step1_has_problem` | bool | `PROBLEM` 역할 컷이 존재하는지 여부. 문제-해결 구조 광고 필터링에 사용 |
| `step2_has_review` | bool | `PROOF`·`TESTIMONIAL` 역할 컷(리뷰·증언 장면)이 존재하는지 여부 |

