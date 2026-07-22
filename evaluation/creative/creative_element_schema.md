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
| 마이그레이션 | — | `LEGACY_TYPE_MAP`/`LEGACY_SUBTYPE_MAP`(clinical_spec_number→spec_number, cg_particle→process_cg)/`LEGACY_CATEGORY_MAP` 을 적재 시 자동 적용 — v1 분석 파일 재추출 불필요 |

판정 기준(60%/30%/고립)과 컬렉션 2개 구조는 변경 없음. 아래 enum 사전은 v1(뷰티 기준) 원본이며,
**현행 enum 의 원천은 코드**(`element_schema.py`·`subtypes_common.py`·`subtypes_packs.py`)다.
아래 사전에서 개명된 이름은 위 매핑표로 읽는다.

## 파이프라인 개요

```
scenario_analysis.json
   │  LLM 추출 (creative_element_analysis.json)
   ▼
vectorDB 적재 (컬렉션 2개)
   ├─ video_creative_profile   ← 영상 1개 = 1레코드 (세그먼트 검색용)
   └─ ad_creative_element      ← 크리에이티브 요소 1개 = 1레코드 (클리셰 집계용)
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

## 컬렉션 1 — `video_creative_profile` (세그먼트 검색용)

메타데이터 (exact/range 필터, 전부 정규화 값):

```jsonc
{
  "video_id": 348,
  "brand_name": "설화수",                    // raw
  "industry_category": "beauty",             // 기존 13종 enum
  "product_category_norm": "skincare",       // skincare|makeup|haircare|bodycare|innerbeauty|device|cleansing|mask|other
  "product_subtype": "essence_serum",        // essence_serum|cream|ampoule|lotion|toner|eye_care|sun_care|...
  "product_category_raw": "스킨케어 (세럼)",  // 원문 보존
  "duration_sec": 15.0,
  "duration_bucket": "15s",                  // 15s|30s|60s|other (14.5s 등 근사값 흡수)
  "placement": "ctv_15s",
  "campaign_objective": "awareness",
  "target_age_min": 20, "target_age_max": 29,
  "target_gender": "female",                 // female|male|unisex
  "narrative_structure": "hook_body_close",
  "appeal_type_primary": "aspiration",       // concept_evaluation 대표값
  "execution_style_primary": "fantasy",
  "message_strategy_primary": "transformational",
  "creative_dedup_key": "sulwhasoo_yunjo_2026a"  // 동일 소재 지면 변형 중복 제거용
}
```

임베딩 문서: 제품 카테고리 원문 / 타겟 페르소나 / 핵심 메시지·USP·포지셔닝 / 훅 전략 /
톤앤무드 요약 / 대표 카피 1~2개.

## 컬렉션 2 — `ad_creative_element` (클리셰 집계용)

**요소 1개 = 레코드 1개.**

```jsonc
{
  // ─ 식별/필터 (메타데이터) ─
  "video_id": 480,
  "element_type": "texture_shot",       // 아래 9종 enum
  "element_subtype": "cream_swirl",     // type별 enum
  "cut_refs": [6],                      // 근거 컷 번호
  // + profile 컬렉션의 필터 키 복제 (product_category_norm, duration_bucket, placement ...)

  // ─ 임베딩 문서 (군집화·유사도용) ─
  "description": "금색 용기 내부 크림이 소용돌이치며 솟아오르는 매크로 샷",
  "production_detail": "컷6에서 매크로 렌즈로 크림 질감 클로즈업, 시각적 임팩트 극대화"
}
```

---

# enum 사전 — element_type 9종 + subtype 정의

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
