# ad-video-analysis DB 테이블 구조 가이드

> 본 문서는 광고영상 라벨링 툴에서 사용하는 DB(ad-video-analysis)의 핵심 테이블 구조를 정리합니다.
> `users`, `video_uploads`, `transnet_cuts` 테이블은 제외합니다.

---

## 1. labeling_assignments (라벨링 배정)

영상별 부서 단위로 라벨링 작업을 배정하는 테이블입니다.

| 컬럼명 | 타입 | 필수 | 기본값 | 설명 |
|--------|------|------|--------|------|
| id | INT | PK | auto_increment | 배정 ID |
| video_id | INT | FK | - | 대상 영상 ID (`video_uploads.id`) |
| assigned_labeler_id | INT | FK, NULL | - | 배정된 라벨러 ID (`users.id`) |
| assigned_by | INT | FK, NULL | - | 배정한 관리자 ID (`users.id`) |
| department | ENUM | O | - | 담당 부서 |
| status | ENUM | O | `waiting` | 작업 상태 |
| created_at | DATETIME | O | now() | 생성 시각 |
| updated_at | DATETIME | O | auto | 수정 시각 |

**UNIQUE 제약**: `(video_id, department)` — 영상 1건당 부서별 1개 배정만 가능

### Department (부서)

| 값 | 설명 |
|----|------|
| `PM` | PM 팀 |
| `VM` | VM 팀 |
| `ETC` | 기타 |

### LabelingStatus (작업 상태)

| 값 | 설명 |
|----|------|
| `waiting` | 대기 (미착수) |
| `in_progress` | 진행 중 |
| `completed` | 완료 |

---

## 2. labeling_data (라벨링 데이터 — 영상 전반 설정)

배정 1건당 1개의 라벨링 데이터를 저장합니다. 영상 전체에 대한 메타 정보 및 분석 결과를 관리합니다.

### 2.1 기본 정보

| 컬럼명 | 타입 | 필수 | 설명 |
|--------|------|------|------|
| id | INT | PK | 라벨링 데이터 ID |
| assignment_id | INT | FK, UNIQUE | 연결된 배정 ID (`labeling_assignments.id`) |
| ad_id | VARCHAR(500) | NULL | 광고 ID |
| duration | FLOAT | NULL | 영상 길이 (초) |
| fps | FLOAT | NULL | 프레임 레이트 |
| inference_time_sec | FLOAT | NULL | AI 추론 시간 (초) |
| stt_full_text | TEXT | NULL | STT 전체 텍스트 |
| gpu_memory_gb | FLOAT | NULL | GPU 메모리 사용량 (GB) |
| parse_success | BOOLEAN | O (기본 true) | AI 파싱 성공 여부 |
| stt_segments | JSON | NULL | STT 세그먼트 데이터 |

### 2.2 Brief (캠페인 기본 정보)

| 컬럼명 | 타입 | 필수 | 설명 | Enum 참조 |
|--------|------|------|------|-----------|
| campaign_objective | VARCHAR(50) | NULL | 캠페인 목적 | `campaign_objective` |
| industry_category | VARCHAR(50) | NULL | 산업 카테고리 | `industry_category` |
| brand_name | VARCHAR(200) | NULL | 브랜드명 | - |
| target_gender | VARCHAR(20) | NULL | 타겟 성별 | `gender` |
| target_age_range | VARCHAR(20) | NULL | 타겟 연령대 (예: "25-44") | - |
| target_interest | JSON | NULL | 타겟 관심사 (문자열 배열) | - |
| placement | VARCHAR(20) | NULL | 플레이스먼트 | `placement` |
| key_message | TEXT | NULL | 핵심 메시지 | - |

#### campaign_objective (캠페인 목적)

| 값 | 설명 |
|----|------|
| `awareness` | 인지도 |
| `consideration` | 고려 |
| `conversion` | 전환 |
| `retention` | 유지 |
| `app_install` | 앱 설치 |
| `traffic` | 트래픽 |

#### industry_category (산업 카테고리)

| 값 | 설명 |
|----|------|
| `food_beverage` | 식품/음료 |
| `beauty_cosmetics` | 뷰티/화장품 |
| `fashion_apparel` | 패션/의류 |
| `tech_electronics` | 기술/전자 |
| `finance_insurance` | 금융/보험 |
| `retail_ecommerce` | 유통/이커머스 |
| `health_wellness` | 건강/웰니스 |
| `automotive` | 자동차 |
| `travel_hospitality` | 여행/호스피탈리티 |
| `education` | 교육 |
| `real_estate` | 부동산 |
| `gaming_entertainment` | 게임/엔터테인먼트 |
| `telecom` | 통신 |

#### gender (타겟 성별)

| 값 | 설명 |
|----|------|
| `male` | 남성 |
| `female` | 여성 |
| `all` | 전체 |

#### placement (플레이스먼트)

| 값 | 설명 |
|----|------|
| `ctv_6s` | CTV 6초 |
| `ctv_15s` | CTV 15초 |
| `ctv_30s` | CTV 30초 |
| `ctv_60s` | CTV 60초 |

### 2.3 서사 판별

| 컬럼명 | 타입 | 필수 | 설명 |
|--------|------|------|------|
| narrative_type | VARCHAR(20) | NULL | 서사 유형 (`NARRATIVE` / `NON_NARRATIVE`) |
| narrative_confidence | FLOAT | NULL | 확신도 (0.0 ~ 1.0) |
| narrative_reasoning | TEXT | NULL | 판별 근거 |

### 2.4 서사 구조

| 컬럼명 | 타입 | 필수 | 설명 | Enum 참조 |
|--------|------|------|------|-----------|
| narrative_structure | VARCHAR(50) | NULL | 서사 구조 | `narrative_structure` |
| creative_style | VARCHAR(50) | NULL | 크리에이티브 스타일 | `creative_style` |
| tagline | TEXT | NULL | 슬로건 | - |

#### narrative_structure (서사 구조)

| 값 | 설명 |
|----|------|
| `problem_agitation_solution` | 문제-자극-해결 |
| `before_after_bridge` | Before-After-Bridge |
| `testimonial_arc` | 증언 아크 |
| `hook_body_close` | Hook-Body-Close |
| `functional_appeal` | 기능 어필 |
| `non_narrative` | 비서사 |

#### creative_style (크리에이티브 스타일)

| 값 | 설명 |
|----|------|
| `problem_solution` | 문제 해결 |
| `emotional_story` | 감성 스토리 |
| `product_showcase` | 제품 쇼케이스 |
| `testimonial` | 증언 |
| `comparison` | 비교 |
| `humor` | 유머 |
| `educational` | 교육적 |
| `lifestyle` | 라이프스타일 |
| `event_promo` | 이벤트 프로모 |
| `brand_film` | 브랜드 필름 |
| `ugc_style` | UGC 스타일 |
| `emotional_appeal` | 감성 어필 |
| `storytelling` | 스토리텔링 |

### 2.5 Hook Strategy

| 컬럼명 | 타입 | 필수 | 설명 | Enum 참조 |
|--------|------|------|------|-----------|
| hook_technique | VARCHAR(50) | NULL | 훅 기법 | `hook_technique` |
| skip_resistance_strategy | VARCHAR(50) | NULL | 스킵 저항 전략 | `skip_resistance` |
| opening_device | TEXT | NULL | 오프닝 디바이스 | - |
| first_frame_element | TEXT | NULL | 첫 프레임 요소 | - |
| speech_in_first_3sec | BOOLEAN | NULL | 첫 3초 음성 노출 여부 | - |
| text_in_first_3sec | BOOLEAN | NULL | 첫 3초 텍스트 노출 여부 | - |
| brand_in_first_3sec | BOOLEAN | NULL | 첫 3초 브랜드 노출 여부 | - |

#### hook_technique (훅 기법)

| 값 | 설명 |
|----|------|
| `question` | 질문 |
| `shock` | 충격 |
| `empathy` | 공감 |
| `visual_impact` | 시각 임팩트 |
| `statement` | 선언 |
| `story` | 스토리 |
| `no_hook` | 훅 없음 |
| `direct_benefit` | 직접 혜택 |
| `celebrity_appearance` | 셀러브리티 등장 |
| `visual_surprise` | 시각 서프라이즈 |
| `social_proof_opening` | 사회적 증거 오프닝 |
| `problem_dramatization` | 문제 극화 |

#### skip_resistance (스킵 저항 전략)

| 값 | 설명 |
|----|------|
| `curiosity_gap` | 호기심 유발 |
| `immediate_value` | 즉시 가치 |
| `emotional_hook` | 감정 훅 |
| `pattern_interrupt` | 패턴 차단 |
| `social_proof` | 사회적 증거 |
| `fear_of_missing` | FOMO |

### 2.6 Audio Visual

| 컬럼명 | 타입 | 필수 | 설명 | Enum 참조 |
|--------|------|------|------|-----------|
| voiceover_type | VARCHAR(20) | NULL | 보이스오버 유형 | `voiceover_type` |
| voiceover_tone | VARCHAR(20) | NULL | 보이스오버 톤 | `voiceover_tone` |
| mute_optimized | BOOLEAN | NULL | 음소거 최적화 여부 | - |
| music_role | VARCHAR(30) | NULL | 음악 역할 | `music_role` |
| music_tempo | VARCHAR(20) | NULL | 음악 템포 | `music_tempo` |
| text_carries_primary_message | BOOLEAN | NULL | 텍스트가 핵심 메시지 전달 여부 | - |

#### voiceover_type (보이스오버 유형)

| 값 | 설명 |
|----|------|
| `narrator` | 나레이터 |
| `character` | 캐릭터 |
| `character_voice` | 캐릭터 보이스 |
| `none` | 없음 |

#### voiceover_tone (보이스오버 톤)

| 값 | 설명 |
|----|------|
| `conversational` | 대화적 |
| `authoritative` | 권위적 |
| `warm` | 따뜻한 |
| `energetic` | 에너지틱 |
| `playful` | 유쾌한 |
| `informative` | 정보적 |
| `comedic` | 코미디 |

#### music_role (음악 역할)

| 값 | 설명 |
|----|------|
| `background_mood` | 배경 무드 |
| `narrative_driver` | 서사 드라이버 |
| `rhythm_driver` | 리듬 드라이버 |
| `emotional_peak` | 감정 피크 |
| `brand_signature` | 브랜드 시그니처 |
| `none` | 없음 |

#### music_tempo (음악 템포)

| 값 | 설명 |
|----|------|
| `slow` | 느림 |
| `moderate` | 보통 |
| `fast` | 빠름 |
| `upbeat` | 업비트 |
| `variable` | 가변적 |
| `none` | 없음 |

### 2.7 Close Strategy

| 컬럼명 | 타입 | 필수 | 설명 | Enum 참조 |
|--------|------|------|------|-----------|
| close_type | VARCHAR(30) | NULL | 클로즈 유형 | `close_type` |
| end_card_elements | JSON | NULL | 엔드카드 요소 (문자열 배열) | `end_card_elements` |
| cta_type | VARCHAR(30) | NULL | CTA 유형 | `cta_type` |
| promo_type | VARCHAR(30) | NULL | 프로모 유형 | `promo_type` |
| promo_detail | TEXT | NULL | 프로모 상세 | - |

#### close_type (클로즈 유형)

| 값 | 설명 |
|----|------|
| `brand_emotion` | 브랜드 감성 |
| `conversion_heavy` | 전환 집중 |
| `promo_driven` | 프로모 중심 |
| `product_showcase` | 제품 쇼케이스 |
| `app_download` | 앱 다운로드 |
| `minimal_logo` | 미니멀 로고 |

#### end_card_elements (엔드카드 요소 — 복수 선택)

| 값 | 설명 |
|----|------|
| `logo` | 로고 |
| `cta_text` | CTA 텍스트 |
| `app_badge` | 앱 배지 |
| `tagline` | 슬로건 |
| `promo_text` | 프로모 텍스트 |
| `qr_code` | QR 코드 |
| `product_image` | 제품 이미지 |

#### cta_type (CTA 유형)

| 값 | 설명 |
|----|------|
| `app_download_badge` | 앱 다운로드 배지 |
| `qr_code` | QR 코드 |
| `url_visit` | URL 방문 |
| `phone_call` | 전화 걸기 |
| `store_visit` | 매장 방문 |
| `custom` | 커스텀 |

#### promo_type (프로모 유형)

| 값 | 설명 |
|----|------|
| `discount_percent` | % 할인 |
| `discount_amount` | 금액 할인 |
| `free_trial` | 무료 체험 |
| `gift` | 사은품 |
| `none` | 없음 |

### 2.8 Message

| 컬럼명 | 타입 | 필수 | 설명 |
|--------|------|------|------|
| primary_message | TEXT | NULL | 핵심 메시지 |
| supporting_messages | JSON | NULL | 보조 메시지 (문자열 배열) |
| message_repetition_count | INT | NULL | 메시지 반복 횟수 |

### 2.9 Pipeline (AI 분석 메타)

| 컬럼명 | 타입 | 필수 | 설명 |
|--------|------|------|------|
| pipeline_model | VARCHAR(100) | NULL | AI 모델명 |
| transnet_threshold | FLOAT | NULL | TransNet 임계값 |
| stt_model | VARCHAR(100) | NULL | STT 모델명 |
| max_cuts | INT | NULL | 최대 컷 수 |

### 2.10 분석 결과 / 기타

| 컬럼명 | 타입 | 필수 | 설명 |
|--------|------|------|------|
| role_sequence | VARCHAR(200) | NULL | 역할 시퀀스 문자열 |
| narrative_summary | TEXT | NULL | 서사 요약 |
| step1_has_problem | BOOLEAN | NULL | Step1 문제 요소 존재 여부 |
| step2_has_review | BOOLEAN | NULL | Step2 리뷰 요소 존재 여부 |
| human_label | JSON | NULL | 사람이 부여한 라벨 데이터 |
| match_data | JSON | NULL | AI-Human 매칭 비교 데이터 |
| key_scenes | JSON | NULL | 핵심 장면 데이터 |
| is_analysis_complete | BOOLEAN | O (기본 false) | 분석 완료 여부 |
| created_at | DATETIME | O | 생성 시각 |
| updated_at | DATETIME | O | 수정 시각 |

---

## 3. labeling_sequences (시퀀스)

영상을 시간 구간별로 나눈 시퀀스 단위입니다. 하나의 labeling_data에 여러 시퀀스가 속합니다.

| 컬럼명 | 타입 | 필수 | 기본값 | 설명 | Enum 참조 |
|--------|------|------|--------|------|-----------|
| id | INT | PK | auto_increment | 시퀀스 PK |
| labeling_data_id | INT | FK | - | 소속 라벨링 데이터 ID |
| sequence_id | INT | O | - | 시퀀스 순번 (1부터) |
| start_sec | DECIMAL(10,2) | O | - | 시작 시간 (초) |
| end_sec | DECIMAL(10,2) | O | - | 종료 시간 (초) |
| role | VARCHAR(30) | NULL | - | 시퀀스 역할 | `narrative_role` |
| role_evidence | TEXT | NULL | - | 역할 판별 근거 | - |
| has_problem_element | BOOLEAN | O | false | 문제 요소 포함 여부 | - |
| has_experience_element | BOOLEAN | O | false | 경험 요소 포함 여부 | - |
| sequence_label | VARCHAR(10) | NULL | - | 시퀀스 라벨 | `sequence_label` |
| intent | VARCHAR(30) | NULL | - | 의도 | `intent` |
| num_cuts | INT | O | 0 | 포함 컷 수 | - |
| delivery | VARCHAR(20) | NULL | - | 전달 방식 | `delivery` |
| brand_visible | BOOLEAN | O | false | 브랜드 노출 여부 | - |
| brand_first_sec | DECIMAL(10,2) | NULL | - | 브랜드 최초 등장 시간 (초) | - |
| product_visible | BOOLEAN | O | false | 제품 노출 여부 | - |
| product_first_sec | DECIMAL(10,2) | NULL | - | 제품 최초 등장 시간 (초) | - |
| product_focus_level | VARCHAR(20) | O | `none` | 제품 포커스 수준 | `product_focus` |
| brand_assets | JSON | NULL | - | 브랜드 자산 (문자열 배열) | `brand_assets` |
| viewable_without_audio | BOOLEAN | NULL | - | 음소거 시 시청 가능 여부 | - |
| legible_at_3m | BOOLEAN | NULL | - | 3m 거리 가독성 | - |
| key_visual | BOOLEAN | O | false | 핵심 비주얼 여부 | - |
| key_scene_location | VARCHAR(20) | NULL | - | 핵심 장면 장소 | `location` |
| key_scene_subject | VARCHAR(30) | NULL | - | 핵심 장면 주체 | `subject` |
| key_scene_describe | TEXT | NULL | - | 핵심 장면 묘사 | - |
| key_scene_memo | TEXT | NULL | - | 핵심 장면 메모 | - |
| memo | TEXT | NULL | - | 메모 | - |
| sort_order | INT | O | 0 | 정렬 순서 | - |
| created_at | DATETIME | O | now() | 생성 시각 | - |
| updated_at | DATETIME | O | auto | 수정 시각 | - |

### narrative_role (서사 역할) — 시퀀스 role 및 컷 narrative_role 공통

| 값 | 설명 |
|----|------|
| `HOOK` | 주의 집중 |
| `ESTABLISH_CONTEXT` | 배경 소개 |
| `PROBLEM` | 문제 제시 |
| `SOLUTION` | 해결책 제시 |
| `FEATURE` | 기능/특장점 |
| `PROOF` | 신뢰 근거 |
| `EXPERIENCE` | 사용 경험 |
| `OUTCOME` | 사용 후 변화 |
| `PROMO` | 할인/이벤트 |
| `CTA` | 행동 유도 |
| `EMOTIONAL_APPEAL` | 감정 공감 |
| `VISUAL_FILLER` | 시각 전환 |
| `BRAND` | 브랜드 마무리 |

### sequence_label (시퀀스 라벨)

| 값 | 설명 |
|----|------|
| `hook` | Hook (도입) |
| `body` | Body (전개) |
| `close` | Close (마무리) |

### intent (의도)

| 값 | 설명 |
|----|------|
| `provoke_curiosity` | 호기심 유발 |
| `create_urgency` | 긴급성 생성 |
| `build_trust` | 신뢰 구축 |
| `demonstrate_value` | 가치 시연 |
| `evoke_aspiration` | 열망 유발 |
| `deliver_information` | 정보 전달 |
| `drive_action` | 행동 유도 |
| `reinforce_brand` | 브랜드 강화 |

### delivery (전달 방식)

| 값 | 설명 |
|----|------|
| `voice_only` | 음성만 |
| `text_only` | 텍스트만 |
| `voice_and_text` | 음성+텍스트 |
| `visual_only` | 시각만 |

### product_focus (제품 포커스 수준)

| 값 | 설명 |
|----|------|
| `none` | 없음 |
| `background` | 배경 |
| `secondary` | 보조 |
| `primary` | 주요 |

### brand_assets (브랜드 자산)

| 값 | 설명 |
|----|------|
| `product` | 제품 |
| `logo` | 로고 |
| `app_ui` | 앱 UI |
| `brand_icon` | 브랜드 아이콘 |
| `brand_character` | 브랜드 캐릭터 |
| `packaging` | 패키징 |

### location (장소)

| 값 | 설명 |
|----|------|
| `indoor` | 실내 |
| `outdoor` | 실외 |
| `studio` | 스튜디오 |
| `cgi` | CGI |
| `mixed` | 혼합 |

### subject (주체)

| 값 | 설명 |
|----|------|
| `person` | 인물 |
| `product` | 제품 |
| `object` | 객체 |
| `environment` | 환경 |
| `person_with_product` | 인물+제품 |
| `abstract` | 추상 |
| `text_graphic` | 텍스트/그래픽 |

---

## 4. labeling_cuts (컷)

시퀀스 내에서 장면 전환 기준으로 분할된 개별 컷 단위입니다. 하나의 시퀀스에 여러 컷이 속합니다.

| 컬럼명 | 타입 | 필수 | 기본값 | 설명 | Enum 참조 |
|--------|------|------|--------|------|-----------|
| id | INT | PK | auto_increment | 컷 PK |
| labeling_data_id | INT | FK | - | 소속 라벨링 데이터 ID |
| sequence_id | INT | O | - | 소속 시퀀스 순번 |
| cut_num | INT | O | - | 컷 번호 (영상 전체 기준 1부터) |
| start_sec | DECIMAL(10,2) | O | - | 시작 시간 (초) |
| end_sec | DECIMAL(10,2) | O | - | 종료 시간 (초) |
| narrative_role | VARCHAR(30) | NULL | - | 서사 역할 | `narrative_role` |
| plot | TEXT | NULL | - | 장면 묘사 | - |
| narration | TEXT | NULL | - | 나레이션/대사 | - |
| text_content | TEXT | NULL | - | 화면 텍스트 | - |
| brand_assets | VARCHAR(30) | NULL | - | 브랜드 자산 (단일 선택) | `brand_assets` |
| memo | TEXT | NULL | - | 메모 | - |
| brand_visible | BOOLEAN | O | false | 브랜드 노출 여부 | - |
| brand_first_sec | DECIMAL(10,2) | NULL | - | 브랜드 최초 등장 시간 (초) | - |
| product_visible | BOOLEAN | O | false | 제품 노출 여부 | - |
| product_first_sec | DECIMAL(10,2) | NULL | - | 제품 최초 등장 시간 (초) | - |
| sort_order | INT | O | 0 | 정렬 순서 | - |
| created_at | DATETIME | O | now() | 생성 시각 | - |
| updated_at | DATETIME | O | auto | 수정 시각 | - |

> `narrative_role`, `brand_assets` enum은 시퀀스 테이블과 동일한 값 목록을 사용합니다 (위 §3 참조).

---

## 테이블 관계 요약

```
labeling_assignments (1) ─── (1) labeling_data
                                    │
                                    ├── (N) labeling_sequences
                                    │
                                    └── (N) labeling_cuts
```

- `labeling_assignments` ↔ `labeling_data`: 1:1 관계 (assignment_id UNIQUE)
- `labeling_data` → `labeling_sequences`: 1:N (labeling_data_id FK)
- `labeling_data` → `labeling_cuts`: 1:N (labeling_data_id FK)
- 컷은 `sequence_id` 값으로 논리적으로 시퀀스에 귀속 (FK 제약 없음, 값 매칭)
- 모든 하위 테이블은 `ON DELETE CASCADE`로 상위 삭제 시 자동 삭제
