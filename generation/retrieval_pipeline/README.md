# generation/retrieval_pipeline 모듈

한 줄 크리에이티브 원칙(예: "기기를 보여주지 말고, 집에서 세계와 연결되는 순간을 보여라.")을
입력받아, **자사 광고 벡터 DB에서 실제로 검색한 참조 광고**를 근거로 연출 장치(device)를
제안하는 파이프라인이다.

> **개편 중(진행형)**: 기존 M3~M7(장치 후보 제안 → 코드가 검색 실행 → 결과 반영 합성 →
> Markdown 렌더링) 설계를 걷어내고 처음부터 다시 설계하고 있다. 지금은 M1(제품·브랜드
> 인사이트 조사)~M5(스토리보드 이미지 슬롯 계획 + Seedance 영상 프롬프트)까지 있다.
> **장치 생성 단계는 원래 M3였다가 M2로 재번호됐고, 비게 된 M3 번호는 새 단계(M2 장치
> 2~4개 조합 → 러프 시나리오 초안 5개)가 가져갔다**(사용자 요청 — "기존 m3 -> m2로 변경하고,
> m3 단계 새롭게 만들거야", 아래 "M2가 M1을 참조하는 방법"·"M3 실행 흐름" 참고). M2는
> legacy M0~M2(v5_m0_m3 재사용 경로) 없이 M1만으로 실행할 수 있다. M1은 M2로는 배선됐지만
> legacy M2(포지셔닝)로는 아직 배선되지 않았고, M3(러프 시나리오 초안)는 아직 M4로 배선되지
> 않았으며, 여러 시나리오 비교/권고·Markdown 렌더링 같은 뒷단계도 아직 없다(사용자 요청 —
> "다 지우고 한단계씩 개발").
>
> M5의 최종 목적은 Seedance(이미지→영상 생성 모델)에 "스토리보드(이미지)"와 "프롬프트
> (텍스트)"를 함께 넣어 실제 광고 영상을 만드는 것이다(사용자 요청). 이미지 소싱/생성 자체는
> 이 파이썬 파이프라인이 아니라 Codex CLI가 한다 — `storyboard_codex.py`는
> `C:\Analysis_workspace\ad_video_analysis\story_board`(별도 프로젝트)의 Codex 구동 방식을
> **import 하지 않고 복사해서 독립적으로** 재구현한 것이다(사용자 요청).

## 단계 개요

| 단계 | 이름 | 산출물 | 비고 |
|------|------|--------|------|
| M1 | 제품·브랜드 인사이트 조사 | `m1.json` | 이 파이프라인의 첫 단계, 새로 설계 |
| M2 | 연출 장치 8개 생성 | `m2.json` | 원래 M3, 사용자 요청으로 재번호. M1만으로 실행 가능 |
| M3 | 러프 시나리오 초안 5개 | `m3.json` | 신규. M2 장치 2~4개씩 조합, 도구 없음. M4와는 독립 경로 |
| M4 | 광고 전체 시나리오 완성 | `m4.json` | M2 산출물을 직접 받는다(M3를 아직 거치지 않음) |
| M5 | 스토리보드 이미지 계획 | `m5.json` + `storyboard.html` | M4 시나리오 기반 |

## v5_m0_m3 와의 관계

- **M1(제품·브랜드 인사이트 조사)은 이 패키지에서 새로 설계한 단계**다(`product_insight.py`).
  v5_m0_m3 의 MODULE 1(JTBD 인사이트)과는 무관한 별개 설계다. URL 크롤링만
  `generation.v5_m0_m3.v1_bridge.parse_url()`(검증된 크롤러)을 유틸리티로 재사용하고, 그
  위의 ProductInfoCard/material_extractor 같은 무거운 레이어는 가져오지 않는다.
- **M0~M2(소재 인제스트→인사이트→포지셔닝, `cli.py` 경로)는 `generation/v5_m0_m3` 와 완전히
  동일한 로직을 그대로 재사용한다** — `cli.py` 는 `generation.v5_m0_m3.pipeline.run_m0_m2()`
  를 그대로 호출할 뿐, M0~M2 를 이 패키지 안에 다시 구현하지 않는다. **이 legacy 경로는 이
  파이프라인의 M2(장치 생성) 실행에 더 이상 필수가 아니다** — M2가 참고할 legacy 포지셔닝
  성명서·JTBD 인사이트가 더 필요할 때만 선택적으로 돌린다(아래 "M2가 M1을 참조하는 방법"
  참고). legacy 모듈 번호(v5_m0_m3 의 M0/M1/M2)와 이 파이프라인의 단계 번호(M1~M5)는 서로
  다른 체계이니 혼동하지 말 것 — 특히 legacy "M2"(포지셔닝)와 이 파이프라인의 "M2"(장치
  생성)는 이름만 같을 뿐 완전히 다른 단계다.
- **M2(장치 8개 생성, 원래 M3)는 이 패키지에서 새로 설계한 단계**다. LLM 호출 인프라는
  v5_m0_m3 와 달리 이 패키지 전용 `tool_chat.py` 를 쓴다(아래 "왜 v5_m0_m3.llm_adapter 를
  그대로 안 쓰는가" 참고). M2 자체는 이제 M1(`cli_m1.py`)의 산출물만으로 실행할 수 있다 —
  `cli.py`(v5_m0_m3 `run_m0_m2()` 재사용)는 legacy 맥락을 보강하고 싶을 때만 선택적으로
  쓴다.
- **M3(러프 시나리오 초안 5개)도 이 패키지에서 새로 설계한 신규 단계**다(`scenario_draft.py`).
  M2의 devices[] 를 코드 그대로 받아 도구 호출 없이 조합만 판단한다.

## M1 실행 흐름 — 크롤링·웹 검색·이미지 분석을 코드가 모은 뒤 LLM이 한 번에 종합

```
M1 product_insight   (LLM 호출 1회 — 도구 없음, 근거 수집은 그 앞에 코드가 결정적으로 수행)
    제품명 + URL + 가이드 문서(선택) + 참조 이미지 폴더(선택)
    → URL 크롤링(v1_bridge.parse_url 재사용)
      → 크롤 html에서 로고(brandlogourl)·제품 이미지(og:image + <img> 후보) 발견 시
        <run_dir>/crawled_images/ 에 저장(logo.*, product_1.* …) — 실패해도 그레이스풀
    → 제품 스펙·사용법·소재 웹 검색(DuckDuckGo)
    → 댓글·리뷰·브랜드 평판 웹 검색(DuckDuckGo)
    → 참조 이미지 외관 분석(OpenAI Vision, call_openai_with_images)
    → 위 네 소스 + 가이드 문서를 "가이드 문서 최우선 → 크롤링/검색 → 추론([가설])" 순서로
      종합해 9개 필드 완성: product_type/appearance/usage_scenarios/features/materials/
      current_brand_image/aspirational_brand_image/target_group/misc_notes
```

`cli_m1.py`가 이 파이프라인의 첫 단계다 — 실행 폴더(`output/retrieval_pipeline/<날짜>_
<제목>/`)를 새로 만드는 것도 이 단계다. M1 산출물(`m1.json`)은 `cli_m2.py --m1_input`으로
넘겨 M2의 주 근거로 쓴다(바로 아래 참고) — legacy M2(포지셔닝) 입력 포맷으로는 아직 배선돼
있지 않다(다음 요청에서 다룬다).

## M2 실행 흐름 — LLM이 스스로 검색하며 장치를 완성한다 (원래 M3)

이전 설계(device_scout(LLM, 검색 없음) → retrieval(코드, 결정적 검색) → synthesis(LLM, 검색
결과 반영))는 "검색은 코드가 결정적으로 실행"하는 방식이었다. 이번 개편은 반대로 **LLM에게
`search_chromadb` 검색 도구를 직접 쥐어주고, 장치 후보를 검증하기 위해 몇 번이든 스스로 검색
판단을 내리게** 한다 — 분석(문제 진단)·검색(도구 호출)·완성(장치 8개)이 LLM 호출 1회 안에서
전부 일어난다.

```
M2 device_generation   (LLM 호출 1회 — 그 안에서 도구 왕복은 여러 번)
    M1 product_insight(주 근거) + 선택적 한 줄 원칙 + 선택적 legacy m0~m2 맥락(보강용)
    → 크리에이티브 문제 진단
    → 1단계: search_chromadb 를 USP·타깃·제품 카테고리 중심 쿼리로 몇 차례 호출해
      이 시장/카테고리에서 이미 쓰인 소구·연출을 넓게 훑어봄
    → 2단계: 그 결과를 보고 장치 후보를 구체화하면서, 더 디테일한 연출 근거가 필요한
      장치마다 구체적인 시각적·구조적 특징을 담은 쿼리로 search_chromadb 를 다시 호출
    → 정확히 장치 8개(근거 인용 포함) 완성
```

### M2가 M1을 참조하는 방법

`cli_m2.py --m1_input <m1.json>`으로 `cli_m1.py`가 만든 M1 산출물을 넘기면 M2의 주 근거가
된다 — `context.build_context()`가 이를 `context.product_insight`(`product_type`/
`appearance`/`usage_scenarios`/`features`/`materials`/`current_brand_image`/
`aspirational_brand_image`/`target_group`/`misc_notes` 9개 필드 그대로)로 얹고,
legacy `module0`/`m1`/`m2`가 없을 때는 `product.name`/`product.category`/
`insight.target_label`의 폴백 소스로도 쓴다. `prompts/m2_system.md`가 이 필드를(외관·
기능·재료·사용법을 장치의 물리적 근거로, 현재/추구 브랜드 이미지를 톤·문제진단 근거로)
반드시 참고하도록 지시한다.

`--m1_input`을 주면 `cli_m2.py`는 그 `m1.json`이 있던 폴더에 그대로 `m2.json`을 이어서
저장한다(`cli_m3.py`/`cli_m4.py`/`cli_m5.py`와 같은 관례) — `--title`도 새 폴더도 필요
없다. `--input`(legacy `m0_m2.json`, `cli.py`가 만든 것)은 이제 완전히 선택이며, 지정하면
`context.product`/`context.insight`/`context.positioning`을 legacy 값으로 보강한다(단,
`--m1_input` 없이 `--input`만 쓰면 기존처럼 `--title`로 새 날짜 폴더를 만든다). `--m1_input`
과 `--input` 중 최소 하나는 있어야 한다.

## M3 실행 흐름 — M2 장치 2~4개 조합 → 러프 시나리오 초안 5개 (신규)

M4(풀 프로덕션 시나리오 1개 완성)보다 훨씬 가벼운 발산 단계다 — 컷 단위 beats 까지 만들지
않고, "이 장치들을 조합하면 대략 이런 이야기가 된다"를 5가지 방향으로 빠르게 비교하기 위한
스케치다(사용자 요청 — "m2의 device를 2~4개정도 조합해서 러프한 시나리오를 5개정도 생성").

```
M3 scenario_draft   (LLM 호출 1회 — 도구 없음, 장치 자체의 근거는 이미 M2에서 끝난 일)
    m2.json(context + creative_problem + devices 8개)
    → devices[] 중 2~4개씩 골라 서로 다른 방향의 조합 5개를 구성
    → 조합마다 name/device_names/narrative(Hook~마무리 러프한 흐름)/hook/why_this_combo/
      concept_fit 완성
    → 정확히 초안 5개
```

`device_generation.py`(M2)와 같은 패턴으로 `tool_chat.run()`을 그대로 재사용한다(README의
선례 — "M5는 검색을 쓰지 않지만 같은 호출 인프라를 재사용"과 동일한 이유, `scenario_draft.py`).
`cli_m3.py`는 새 날짜 폴더를 만들지 않고 `--input`(`m2.json`)이 있던 폴더에 `m3.json`으로
이어서 저장한다(`cli_m4.py`와 같은 관례).

**M4와는 독립적인 별개 경로다** — 지금 M4는 이 초안을 거치지 않고 `m2.json`을 직접 받는다.
초안 5개 중 하나를 골라 M4로 넘기는 배선은 아직 없다(다음 요청에서 다룬다 — "한단계씩
개발").

## M4 실행 흐름 — M2 장치 중 골라 조합해 광고 전체 시나리오 완성

```
M4 scenario_generation   (LLM 호출 1회 — search_chromadb 도구 왕복은 선택적)
    m2.json(M1 인사이트/legacy 맥락 + creative_problem + devices 8개)
    → 이 제품·광고 길이에 맞는 장치를 몇 개 골라 하나의 내러티브로 조합
    → (필요하면) search_chromadb 로 이 길이/카테고리의 컷 구성·페이싱을 참고
      — 장치 자체의 근거는 이미 M2에서 끝난 일이라 의무는 아니다
    → cast/scenes(cut_index·time·beats)/key_messages/production_notes/devices_applied 완성
      (output/total/*/scenario_analysis.json 과 동일한 구조 + devices_applied 만 추가)
```

M2와 같은 이유로 device_generation.py 를 그대로 재사용하지 않고 `scenario_generation.py` 를
따로 뒀다(출력 스키마가 다르고, 이번 단계는 검색이 선택적이라 프롬프트 지시 자체가 다르다).
`tool_chat.py`(search_chromadb 자율 호출 왕복 루프)는 M2·M4가 그대로 공유한다.

## M5 실행 흐름 — M4 시나리오를 스토리보드 이미지 계획 + Seedance 프롬프트로 전환

```
M5 storyboard_generation   (LLM 호출 1회 — search_chromadb 는 쓰지 않는다)
    m4.json(시나리오: cast/scenes) + module0 제품 사실
    → 인물마다 정면/측면/의상 착용 3장의 "이미지 생성 프롬프트"(콘셉트 캐스팅이라 생성)
    → 제품은 컷1~3+로고 4장의 "소싱 브리프"(실물이어야 하므로 생성이 아니라
      "이 슬롯이 무엇을 보여줘야 하는가"만 정한다 — 사용자가 공급한 사진을 우선 쓰고
      부족한 각도는 크롤링으로 찾는다)
    → Environment 1장의 "이미지 생성 프롬프트"
    → 컷마다 keyframe_image_prompt(정지 이미지 생성 프롬프트) + seedance_prompt(그 키프레임
      에서 영상이 어떻게 움직이는지만 서술하는 모션 텍스트, 정적 외형은 반복하지 않음)
    → storyboard_template.py 가 이 계획과 같은 슬롯 캡션(예: "캐릭터1 · 정면", "컷3")을 쓴
      storyboard.html(generation/AITIVE_스토리보드_틀.html 을 실제 인물 수·컷 수로 인스턴스화)
      을 별도로 생성
```

`cli_m5.py`는 여기까지만 한다(이미지 생성 없음, LLM 호출 1회라 저렴하고 빠르다). 실제 이미지
소싱/생성은 별도로 `storyboard_codex.py`를 실행해야 한다(Codex CLI, 비용·시간이 드는 별도
단계라 의도적으로 분리 — story_board 프로젝트의 원래 구조도 HTML 준비와 Codex 실행이
분리돼 있었다):

```bash
python -m generation.retrieval_pipeline.storyboard_codex \
    --input_html output/retrieval_pipeline/<날짜>_<제목>/storyboard.html \
    --shot_plan  output/retrieval_pipeline/<날짜>_<제목>/m5.json \
    --output_dir output/retrieval_pipeline/<날짜>_<제목>/codex_output \
    [--reference_dir <사용자 제품 사진 폴더>] [--dry_run]
```

`storyboard_codex.py`가 하는 일:
- `m5.json`의 슬롯별 지시문(인물=생성, 제품=소싱, Environment=생성, 컷=생성)을 캡션
  문자열("캐릭터1 · 정면" 등)로 매칭해 Codex 프롬프트에 그대로 박아 넣는다 — Codex가 빈 HTML
  문구를 해석해서 추측하지 않는다.
- 제품 슬롯은 `--reference_dir`(사용자 공급 사진)를 먼저 확인하고, 부족한 각도만 공식
  소스를 웹에서 조사해 보완하도록 지시한다(지어내지 않음).
- **사람이 등장하는 모든 이미지에서 얼굴을 강한 블러로 익명 처리한다**(인물 슬롯 + 컷별
  슬롯 모두, story_board 원본 정책과 동일 — 사용자 요청) — 스토리보드는 리뷰용 산출물이라
  식별 가능한 얼굴을 남기지 않는다. 목·쇄골 등 얼굴 밖 부위(주얼리라면 착용 부위)는 가리지
  않는다.
- `m5.json`의 `cuts[].seedance_prompt`를 Codex 없이 파이썬이 직접
  `<output_dir>/seedance_prompts.json`에 그대로 옮겨 적는다(사용자 요청 — "필요한 이미지
  정보는 스토리보드에 담고 텍스트 정보들은 prompt에 적어줘": 이미지는 Codex가 채운
  `completed.html`/`assets/`에, 텍스트는 이 JSON에 분리해서 낸다).
- `storyboard_image_layout.py`(story_board에서 그대로 복사, 순수 stdlib+ffmpeg)로 각 슬롯이
  카테고리별 비율(인물 4:5, 제품/환경 1:1, 컷 6:5)을 따르는 적응형 레이아웃 패스를 강제한다.

### 왜 v5_m0_m3.llm_adapter 를 그대로 안 쓰는가

`generation/v5_m0_m3/llm_adapter.py` 는 stage 별로 고정된 kind(`concept`→`ad_concept_reference`,
`production`→`ad_production_reference`)에 맞춰 검색 도구와 컬렉션명을 미리 정해준다. 이
파이프라인은 매 검색 호출마다 `category_analysis`/`scenario_analysis` 둘 중 어느 쪽을 쓸지
**LLM 이 그때그때 스스로 판단**해야 해서(kind 1개당 컬렉션 1개 고정이라는 그 인프라의 전제와
안 맞는다) 재사용하지 않고 `tool_chat.py` 에 독립적으로 구현했다. 노출하는 도구 자체는 이미
컬렉션명을 인자로 받는 범용 `db.chromadb.tool_definitions.search_chromadb` 하나뿐이라
kind 배정이 필요 없다.

## 코드와 프롬프트 분리

시스템/유저 프롬프트 문구는 전부 `prompts/*.md` 에 있고, 코드는 `{{변수}}` 채우기
(`prompt_loader.py`)와 LLM 호출·파싱만 한다 — 실제로 모델에 무엇이 어떤 순서로 들어가는지
`.py` 를 안 읽고 `.md` 만 봐도 알 수 있다.

| 프롬프트 파일 | 역할 | 채워지는 변수 |
|------|------|------|
| `prompts/m1_common.md` | 페르소나(제품·브랜드 리서치 애널리스트) + 근거 우선순위 원칙 | (없음) |
| `prompts/m1_system.md` | 지시문 — 9개 필드(product_type/appearance/usage_scenarios/features/materials/current_brand_image/aspirational_brand_image/target_group/misc_notes) 정의 | (없음) |
| `prompts/m1_user.md` | 입력 | `product_name`, `url`, `guideline_md`, `crawled_title`, `crawled_text`, `product_research`, `comment_research`, `image_notes` |
| `prompts/m2_common.md` | 페르소나(레퍼런스 리서치 디렉터) | (없음) |
| `prompts/m2_system.md` | 지시문 — 문제 진단 + 도구로 근거 수집 + 장치 8개 완성 | (없음) |
| `prompts/m2_user.md` | 입력 | `concept_line`, `ad_length`, `context_json` |
| `prompts/m3_common.md` | 페르소나(광고 크리에이티브 디렉터) — 장치 조합/발산 원칙 | (없음) |
| `prompts/m3_system.md` | 지시문 — M2 장치 2~4개 조합 + 러프 시나리오 초안 5개 완성 | (없음) |
| `prompts/m3_user.md` | 입력 | `concept_line`, `ad_length`, `creative_problem`, `devices_json`, `context_json` |
| `prompts/m4_common.md` | 페르소나(시나리오 디렉터) | (없음) |
| `prompts/m4_system.md` | 지시문 — 장치 선택/조합 + (선택)도구로 페이싱 참고 + 시나리오 완성 | (없음) |
| `prompts/m4_user.md` | 입력 | `concept_line`, `ad_length`, `creative_problem`, `devices_json`, `context_json` |
| `prompts/m5_common.md` | 페르소나(영상 제작 파이프라인의 스토리보드 플래너) — 이미지/영상 프롬프트 분리 원칙 | (없음) |
| `prompts/m5_system.md` | 지시문 — 인물/제품/Environment/컷별 이미지 계획 + 컷별 Seedance 모션 프롬프트 완성 | (없음) |
| `prompts/m5_user.md` | 입력 | `scenario_json`, `product_json` |

## 파일 구성

| 파일 | 역할 |
|------|------|
| `cli.py` | legacy M0~M2 진입점(`--url`, v5_m0_m3.pipeline.run_m0_m2 재호출) — M2에 `--input`으로 선택적으로만 얹는 보강용 경로 |
| `cli_m1.py` | M1 진입점(`--product_name` `--url` `--title` `--guideline`(선택) `--reference_dir`(선택) `--llm_backend` `--output_dir`) — 날짜 폴더를 새로 만드는 이 파이프라인의 첫 단계 |
| `product_insight.py` | M1 — 크롤링(`v1_bridge.parse_url` 재사용, 발견한 로고·제품 이미지는 `crawled_images/`에 저장)+DuckDuckGo 웹 검색(제품 스펙/댓글·평판 2종)+참조 이미지 분석(`utils.openai_caller.call_openai_with_images`) + 프롬프트 조립 + `tool_chat.run()` 호출 + `ProductInsight` 파싱 |
| `cli_m2.py` | M2 진입점(`--m1_input <m1.json>`과 `--input <legacy m0_m2.json>` 중 최소 하나 `--concept`(선택) `--title`(`--m1_input` 없을 때만 필수) `--ad_length` `--llm_backend` `--output_dir`) — `--m1_input`을 주면 그 폴더에 이어서 저장. 원래 `cli_m3.py`였다 |
| `device_generation.py` | M2 — 프롬프트 조립 + `tool_chat.run()` 호출 + `DeviceGenerationOutput` 파싱. 원래 이 파이프라인의 M3 |
| `cli_m3.py` | M3 진입점(`--input <m2.json>` `--concept`(선택, 재지정용) `--llm_backend`) — `--input`과 같은 폴더에 `m3.json` 이어서 저장. 신규(M2 장치 조합 → 러프 시나리오 초안 5개) |
| `scenario_draft.py` | M3 — 프롬프트 조립(도구 없음) + `tool_chat.run()` 호출 + `ScenarioDraftOutput` 파싱 |
| `cli_m4.py` | M4 진입점(`--input <m2.json>` `--llm_backend`, `--input`과 같은 폴더에 저장) |
| `cli_m5.py` | M5 진입점(`--input <m4.json>` `--llm_backend`) — `m5.json` + `storyboard.html` 생성 |
| `pipeline.py` | `run_m1()` / `run_m0_m2`(재노출) / `run_m2()` / `run_m3()` / `run_m4()` / `run_m5()` 오케스트레이션 |
| `context.py` | m1_insight(주 근거) + 선택적 legacy module0/m1/m2 → M2 프롬프트용 압축 맥락(`build_context`) |
| `scenario_generation.py` | M4 — 프롬프트 조립(+ module0 원본으로 product.name/usp_candidates 보정) + `tool_chat.run()` 호출 + `AdScenarioOutput` 파싱 |
| `storyboard_generation.py` | M5 — 프롬프트 조립(module0 원본에서 압축한 제품 맥락 포함) + `tool_chat.run()` 호출 + `StoryboardShotPlan` 파싱 |
| `storyboard_template.py` | M5 — `AITIVE_스토리보드_틀.html`을 실제 인물 수·컷 수로 인스턴스화하는 순수 Python HTML 빌더(`render_storyboard_html`/`render_from_shot_plan`) |
| `storyboard_codex.py` | M5 뒷단계 — Codex CLI를 non-interactive로 구동해 `storyboard.html`의 이미지 슬롯을 `m5.json` 계획대로 채운다(story_board 프로젝트에서 복사·독립 재구현, import 아님) |
| `storyboard_image_layout.py` | M5 뒷단계 — 슬롯이 카테고리별 비율을 따르게 만드는 적응형 레이아웃 도구(story_board에서 그대로 복사, stdlib+ffmpeg만 사용) |
| `tool_chat.py` | LLM이 `search_chromadb` 를 tool_use 로 자율 호출하는 왕복 루프(cli: MCP, api: Anthropic 네이티브 tool_use) — M2·M4가 공유(M3·M5는 검색을 쓰지 않지만 같은 호출 인프라를 재사용) |
| `prompt_loader.py` | `prompts/*.md` 로더 + `{{변수}}` 치환(이 패키지 전용) |
| `schemas.py` | `ProductInsight`(M1) + `DeviceGenerationOutput`/`Device`/`ReferenceAdCitation`(M2) + `ScenarioDraftOutput`/`ScenarioDraft`(M3) + `AdScenarioOutput`/`CastMember`/`Scene`/`SceneBeat`/`DeviceUsage`(M4) + `StoryboardShotPlan`/`CharacterShotPrompts`/`ProductShotBriefs`/`EnvironmentShotPrompt`/`CutShotPlan`(M5) pydantic 모델 |
| `prompts/` | 위 표 참고 |
| `../../generation/AITIVE_스토리보드_틀.html` | M5가 인스턴스화하는 빈 이미지 슬롯 틀(원본, 사람이 직접 보고 확인용) |

## 사용법

```bash
# 1) M1 (제품·브랜드 인사이트 조사 — 이 파이프라인의 첫 단계, 실행 폴더를 여기서 만든다)
python -m generation.retrieval_pipeline.cli_m1 \
    --product_name "제품명" --url <제품 상세페이지 URL> --title "DBH_15초_CTV" \
    [--guideline <가이드라인.md>] [--reference_dir <참조 이미지 폴더>] \
    [--llm_backend cli|api] [--output_dir output/retrieval_pipeline]

# 2) M2 (M1 인사이트를 근거로 분석 + 도구 호출로 연출 장치 8개 완성)
python -m generation.retrieval_pipeline.cli_m2 \
    --m1_input output/retrieval_pipeline/<날짜>_DBH_15초_CTV/m1.json \
    [--input <legacy m0_m2.json — 선택, legacy 포지셔닝/JTBD 인사이트로 보강할 때만>] \
    [--concept "기기를 보여주지 말고, 집에서 세계와 연결되는 순간을 보여라."] \
    [--ad_length 15초] [--llm_backend cli|api]

# 3) M3 (선택 — M2 장치 2~4개 조합 → 러프 시나리오 초안 5개, M4와는 독립 경로)
python -m generation.retrieval_pipeline.cli_m3 \
    --input output/retrieval_pipeline/<날짜>_DBH_15초_CTV/m2.json \
    [--concept "..."] [--llm_backend cli|api]

# 4) M4 (M2 장치 조합 → 광고 전체 시나리오 완성)
python -m generation.retrieval_pipeline.cli_m4 \
    --input output/retrieval_pipeline/<날짜>_DBH_15초_CTV/m2.json \
    [--llm_backend cli|api]

# 5) M5 (M4 시나리오 → 스토리보드 이미지 슬롯 계획 + Seedance 모션 프롬프트)
python -m generation.retrieval_pipeline.cli_m5 \
    --input output/retrieval_pipeline/<날짜>_DBH_15초_CTV/m4.json \
    [--llm_backend cli|api]

# 6) M5 뒷단계 (별도 실행 — Codex CLI로 실제 이미지 소싱/생성)
python -m generation.retrieval_pipeline.storyboard_codex \
    --input_html output/retrieval_pipeline/<날짜>_DBH_15초_CTV/storyboard.html \
    --shot_plan  output/retrieval_pipeline/<날짜>_DBH_15초_CTV/m5.json \
    --output_dir output/retrieval_pipeline/<날짜>_DBH_15초_CTV/codex_output \
    [--reference_dir <사용자 제품 사진 폴더>] [--dry_run]
```

3)번(M3, 러프 시나리오 초안)은 완전히 선택이다 — 지금은 4)번(M4)이 3)번을 거치지 않고
2)번(M2) 산출물을 직접 받으므로, 3)번을 건너뛰어도 나머지 파이프라인은 그대로 동작한다.

legacy M0~M2(`cli.py`, v5_m0_m3 `run_m0_m2()` 재사용)를 굳이 돌려 M2 맥락을 보강하고
싶다면: `python -m generation.retrieval_pipeline.cli --url <URL> [--producttitle "제품명"]
[--llm_backend cli|api]`. 산출물(`<label>_m0_m2.json`)을 위 2) 단계의 `--input`으로 넘기면
된다 — M2 실행에 더 이상 필수는 아니다.

| 옵션(`cli_m1.py`) | 기본값 | 설명 |
|------|--------|------|
| `--product_name` | (필수) | 제품명 |
| `--url` | (필수) | 제품 상세페이지 URL |
| `--title` | (필수) | 출력 폴더명에 쓸 프로젝트 제목(슬러그화) |
| `--guideline` | (없음, 선택) | 브랜드 가이드라인 md 경로 — 최우선 근거로 프롬프트에 삽입 |
| `--reference_dir` | (없음, 선택) | 참조 이미지 폴더(여러 장) — OpenAI Vision으로 외관 분석 |
| `--llm_backend` | `cli` | `cli`(claude -p) \| `api`(Anthropic API, `env/api.env` `ANTHROPIC_API_KEY`) |
| `--output_dir` | `output/retrieval_pipeline` | 이 아래 `<날짜>_<제목>/` 폴더가 생긴다(이 파이프라인의 새 첫 단계라 여기서 폴더를 만든다) |

| 옵션(`cli_m2.py`) | 기본값 | 설명 |
|------|--------|------|
| `--m1_input` | (없음, `--input`과 최소 하나 필수) | `cli_m1.py`가 만든 `m1.json` — M2의 주 근거(`context.product_insight`). 주면 그 폴더에 `m2.json`을 이어서 저장한다(`--title`/새 폴더 불필요) |
| `--input` | (없음, `--m1_input`과 최소 하나 필수) | legacy `<slug>_m0_m2.json`(module0/m1/m2) — `--m1_input`을 보강할 때만. `--m1_input` 없이 이것만 쓰면 `--title`로 새 날짜 폴더를 만든다(기존 동작) |
| `--concept` | (없음, 선택) | 한 줄 크리에이티브 원칙 — 안 주면 M1 인사이트(브랜드 이미지 격차·타겟)나 legacy 포지셔닝 성명서·가치 제안에서 LLM이 직접 도출 |
| `--title` | (없음, `--m1_input` 없을 때만 필수) | 출력 폴더명에 쓸 프로젝트 제목(슬러그화) — `--m1_input`을 주면 그 폴더를 그대로 쓰므로 생략 가능 |
| `--ad_length` | `15초` | 스토리라인 길이 |
| `--llm_backend` | `cli` | `cli`(claude -p + chromadb-explorer MCP) \| `api`(Anthropic API 직접 tool_use, `env/api.env` `ANTHROPIC_API_KEY`) |
| `--output_dir` | `output/retrieval_pipeline` | `--m1_input` 없이 새 폴더를 만들 때만 쓰는 상위 경로 — 이 아래 `<날짜>_<제목>/` 폴더가 생긴다 |

| 옵션(`cli_m3.py`) | 기본값 | 설명 |
|------|--------|------|
| `--input` | (필수) | `m2.json`(context/creative_problem/devices 8개 포함) |
| `--concept` | (없음, 선택) | 한 줄 크리에이티브 원칙 재지정 — 안 주면 `m2.json`의 `concept_line`을 그대로 쓴다 |
| `--llm_backend` | `cli` | M2와 동일 |

`cli_m3.py`는 새 날짜 폴더를 만들지 않는다 — `--input`(`m2.json`)이 있던 폴더에 `m3.json`을
이어서 저장한다(도구를 안 쓰므로 검색 로그 파일은 생기지 않는다).

| 옵션(`cli_m4.py`) | 기본값 | 설명 |
|------|--------|------|
| `--input` | (필수) | `m2.json`(module0/m1/m2/context/creative_problem/devices 포함) |
| `--llm_backend` | `cli` | M2와 동일 |

`cli_m4.py`는 새 날짜 폴더를 만들지 않는다 — `--input`(`m2.json`)이 있던 폴더에 `m4.json`을
이어서 저장하고, `search_chromadb` 호출 로그(선택적으로 쓰였다면)도 같은 폴더에
`<제목슬러그>_m4.jsonl`로 남긴다(M2 로그 `<제목슬러그>.jsonl`과 파일이 섞이지 않도록 접미사
구분).

| 옵션(`cli_m5.py`) | 기본값 | 설명 |
|------|--------|------|
| `--input` | (필수) | `m4.json`(module0/m1/m2/context/creative_problem/devices + 시나리오 필드 포함) |
| `--llm_backend` | `cli` | M2·M4와 동일 |

`cli_m5.py`도 `--input`(`m4.json`)이 있던 폴더에 `m5.json`/`storyboard.html`을 이어서
저장한다. 이미지 생성이 없는 순수 LLM 1회 호출이라 검색 로그는 남기지 않는다(prompt에
`search_chromadb`를 아예 언급하지 않음).

| 옵션(`storyboard_codex.py`) | 기본값 | 설명 |
|------|--------|------|
| `--input_html` | (필수) | `cli_m5.py`가 만든 `storyboard.html` |
| `--shot_plan` | (필수) | `cli_m5.py`가 만든 `m5.json`(module0 포함 — 제품 사실 근거로도 쓰인다) |
| `--output_dir` | (필수) | Codex 산출물을 저장할 폴더(자동 생성) |
| `--reference_dir`(`--refernece_dir`도 허용) | (없음, 선택) | 사용자가 공급한 실제 제품 사진 폴더 — 제품 슬롯 소싱에 최우선으로 쓰인다 |
| `--sandbox` | `danger-full-access` | `codex exec --sandbox` 값 — 아래 "Windows 샌드박스 문제" 참고 |
| `--model` | (Codex 기본값) | Codex 실행 모델 |
| `--codex_bin` | (자동 탐색) | Codex 실행 파일 경로/이름 |
| `--extra_instruction` | (없음) | 기본 프롬프트 뒤에 덧붙일 추가 지시 |
| `--keep_session` | `False` | Codex 세션 기록 유지(기본은 `--ephemeral`) |
| `--dry_run` | `False` | Codex를 실행하지 않고 명령/프롬프트만 출력 |

## 출력 구조

`--title "DBH_15초_CTV"` 로 오늘(예: 2026-08-07) 실행하면:

```
output/retrieval_pipeline/20260807_DBH_15초_CTV/
├── m1.json                  {product_name, url, guideline_md, prompt, crawled_images[], product_type,
│                             appearance, usage_scenarios[], features[], materials[], current_brand_image,
│                             aspirational_brand_image, target_group, misc_notes[]}
│                             ※ --m1_input 으로 M2의 주 근거로 넘긴다(아래 참고), legacy M2 입력으론 아직 배선 안 됨
├── crawled_images/          크롤링 중 발견한 로고·제품 이미지(logo.*, product_1.* …) — 아무것도 못 찾았으면 폴더 자체가 안 생긴다
├── m2.json                  {concept_line, ad_length, context, prompt, creative_problem, devices[]}
│                             module0/m1/m2/m1_insight 원본은 저장하지 않는다(사용자 요청 —
│                             build_context() 가 뽑아낸 압축본이 이미 context 에 다 있다)
│                             context.product_insight: --m1_input 을 줬을 때만 생기는 압축 필드(9개, m1.json 필드와 동일)
├── DBH_15초_CTV.jsonl       search_chromadb 호출 로그(M2, 쿼리·컬렉션·검색 결과 원본, 호출마다 한 줄)
├── m3.json                  {concept_line, ad_length, context, creative_problem, devices[], prompt, drafts[]}
│                             (선택 산출물 — cli_m3.py 를 돌렸을 때만 생긴다) drafts[] 원소:
│                             {name, device_names[](2~4개), narrative, hook, why_this_combo, concept_fit} × 5
├── m4.json                  {module0, m1, m2, concept_line, ad_length, context, prompt(M4), creative_problem, devices[],
│                             title, brand, concept, narrative, cast[], scenes[], key_messages[], production_notes, devices_applied[]}
│                             module0/m1/m2: m2.json 에 없으므로 cli_m4.py 는 항상 {}로 채워 넘긴다(legacy 전용 필드, 사실상 미사용)
│                             ※ m2.json 을 직접 받는다 — 위 m3.json(초안 5개)은 아직 이 단계 입력으로 배선 안 됨
├── DBH_15초_CTV_m4.jsonl    search_chromadb 호출 로그(M4, 컷 구성/페이싱 참고용 — 안 썼으면 파일 자체가 안 생긴다)
├── m5.json                  {…m4.json 필드 그대로 + prompt(M5), scenario(=m4.json의 시나리오 필드만 압축),
│                             characters[], product, environment, cuts[]}
├── storyboard.html          AITIVE_스토리보드_틀.html 을 이 프로젝트 인물 수·컷 수로 인스턴스화(이미지 없음)
└── codex_output/            storyboard_codex.py 를 별도 실행했을 때만 생기는 폴더(아래 참고)
    ├── completed.html       storyboard.html 에 이미지가 채워진 최종본
    ├── completed.png        completed.html 전체 페이지 캡처
    ├── assets/              Codex가 생성/크롭한 이미지 파일들
    ├── references/          Codex가 조사에 실제로 쓴 제품 자료 원본 + sources.json(메타데이터)
    ├── image-layout.json / image-layout-report.json   storyboard_image_layout.py 입출력
    ├── seedance_prompts.json   {cut_index, seedance_prompt}[] — m5.json의 컷별 모션 텍스트를 그대로 옮김
    ├── codex-last-message.txt Codex의 최종 응답 텍스트
    └── completed-package.zip  위 산출물을 묶은 배포용 ZIP
```

로그 파일명은 `--title` 슬러그(`log_prefix`)를 그대로 쓴다(사용자 요청, M4는 여기에 `_m4`
접미사를 붙여 M2 로그와 분리). `db.chromadb.tool_definitions.search_chromadb()`(기본 위치
`logs/search_chromadb/`)에 `SEARCH_CHROMADB_LOG_DIR` 환경변수로 이 실행의 출력 폴더를
지정해, 검색 로그가 산출물(`m2.json`/`m4.json`)과 같은 날짜 폴더 안에 남게 한다
(`tool_chat.py`) — 자세한 메커니즘은 [`../../db/README.md`](../../db/README.md)의 "호출 로깅"
절 참고.

`devices[]` 원소 하나(`Device`, `schemas.py`):

```json
{
  "name": "...", "mechanism": "...", "why_it_works": "...",
  "reference_ads": [{"video_id": 123, "collection": "category_analysis"}],
  "reference_thinking": "참조광고를 보니 ~하므로 ~의 ~를 가지고와서 ~하게 적용한다",
  "application_draft": "...", "impact": 4, "production_difficulty": "mid", "concept_fit": 5
}
```

`m3.json` 의 `drafts[]` 원소 하나(`ScenarioDraft`, `schemas.py`):

```json
{
  "name": "...", "device_names": ["시간압축 모프컷", "정적 대비 클로즈업"],
  "narrative": "Hook부터 마무리까지 러프한 흐름 3~5문장...",
  "hook": "도입 3초 아이디어...", "why_this_combo": "두 장치가 왜 같이 쓰일 때 강한지...",
  "concept_fit": 4
}
```

`m4.json` 의 시나리오 필드(`AdScenarioOutput`, `schemas.py`) — `output/total/*/
scenario_analysis.json` 과 동일한 구조에 `devices_applied[]` 만 추가된 형태:

```json
{
  "title": "...", "brand": "...", "concept": "...", "narrative": "...",
  "cast": [{"id": "캐릭터1", "description": "..."}],
  "scenes": [
    {"cut_index": 1, "time": "0.00~1.10s",
     "beats": [{"type": "background", "description": "..."},
               {"type": "action", "cast": "캐릭터1", "description": "..."}]}
  ],
  "key_messages": ["..."],
  "production_notes": "...",
  "devices_applied": [{"device_name": "시간압축 모프컷", "cut_indices": [1, 2], "how_applied": "..."}]
}
```

`m5.json` 의 계획 필드(`StoryboardShotPlan`, `schemas.py`) — 인물/환경/컷은 이미지 생성
프롬프트, 제품은 소싱 브리프(실물 우선)라는 점이 다르다(모듈 docstring 참고):

```json
{
  "characters": [
    {"id": "캐릭터1", "front_prompt": "...", "profile_prompt": "...", "costume_prompt": "..."}
  ],
  "product": {
    "shot_briefs": ["정면 히어로 앵글...", "펀칭 디테일 클로즈업...", "실제 착용 순간..."],
    "logo_brief": "브랜드 로고를 왜곡 없이 실물 그대로 근접 촬영..."
  },
  "environment": {"prompt": "..."},
  "cuts": [
    {"cut_index": 1,
     "keyframe_image_prompt": "그 컷의 정지 구도(정적 정보) — 인물/제품/공간 외형 포함",
     "seedance_prompt": "그 키프레임에서 카메라·동작이 어떻게 전개되는지(동적 정보만)"}
  ]
}
```

## 사전 준비

M1은 `--reference_dir`로 참조 이미지를 넘기면 `utils.openai_caller.call_openai_with_images()`
(OpenAI Vision)를 호출하므로 `env/api.env`의 `OPENAI_API_KEY`가 필요하다(v5_m0_m3 의
M0가 이미 요구하는 것과 동일한 키 — 새 의존성 아님). `--reference_dir`를 안 주면 이미지
분석 단계 자체를 건너뛴다. 웹 검색(DuckDuckGo)은 별도 API 키가 필요 없다.

M2는 검색 없이 실행할 수 없으므로, `data/category_analysis/`·`data/scenario_analysis/` 에 두
컬렉션이 이미 적재돼 있어야 한다:

```bash
python -m db.chromadb.importers.category [--data_root output/total]
python -m db.chromadb.importers.scenario [--data_root output/total]
```

(`../../db/README.md` 참고.) 컬렉션이 비어 있으면 검색 결과가 항상 0건으로 나오고, LLM은
"레퍼런스 미발견 — 원칙만 적용"으로 devices 를 채운다(하드 실패하지 않음). M4는 검색이
선택적이라 컬렉션이 비어 있어도 시나리오 자체는 완성된다 — 다만 컷 구성·페이싱을 참고할
근거가 없을 뿐이다. M3(러프 시나리오 초안)는 도구를 아예 쓰지 않으므로 컬렉션 적재와 무관하다.

`--llm_backend cli` 를 쓰려면 저장소 루트 `.mcp.json`의 `chromadb-explorer` MCP 서버를 최초
1회 승인해야 한다(`db/README.md` "Claude CLI(MCP)" 절 참고, M2·M4 공통). `--llm_backend api`
를 쓰려면 `env/api.env` 의 `ANTHROPIC_API_KEY` 가 필요하다. M3·M5(`cli_m3.py`/`cli_m5.py`)는
이미지 생성이 없는 순수 텍스트 LLM 호출이라 이 두 가지만 있으면 된다.

`storyboard_codex.py`(M5 뒷단계)는 별도로 준비가 필요하다:
- Codex CLI가 설치돼 PATH에서 찾을 수 있어야 하고(`codex`/`codex.cmd`/`codex.exe`), 로그인돼
  있어야 한다 — 실제로 브라우징·이미지 생성 권한이 있는 계정이어야 제품 소싱/인물 생성이
  동작한다.
- `storyboard_image_layout.py`(적응형 레이아웃 패스)가 `ffmpeg`를 PATH에서 호출하므로 미리
  설치해 둬야 한다.
- 제품 사진을 사용자가 직접 공급하려면 `--reference_dir`로 그 폴더를 넘긴다(선택) — 안
  넘기면 Codex가 처음부터 웹 조사만으로 소싱한다.

### Windows 샌드박스 문제 — `--sandbox` 기본값이 `danger-full-access`인 이유

이 환경(Codex CLI 0.146.0, Windows 11)에서 `codex exec --sandbox workspace-write`는
`~/.codex/config.toml`의 `[windows] sandbox` 값에 따라 아예 실행되지 않는 걸 직접 재현해서
확인했다:
- `sandbox = "elevated"`(이 환경의 기존 설정값) — 사전에 `codex sandbox setup --elevated`로
  별도 헬퍼 프로세스를 띄워두지 않으면 모든 파일 작업이 `timed out ... connecting runner
  pipe-in`으로 멈춘다(사용자가 실제로 겪은 에러).
- `-c windows.sandbox="unelevated"`(restricted-token 방식) — 이 방식은 유일한 쓰기 루트만
  지원하는데 `workspace-write`는 기본적으로 workdir+시스템 tmp 두 루트를 함께 쓰기 가능하게
  만들어서(`sandbox: workspace-write [workdir, /tmp, $TMPDIR]`) `refusing to run
  unsandboxed`로 모든 명령이 즉시 거부된다.
- `--sandbox danger-full-access`만 OS 수준 래퍼 자체를 건너뛰어 정상 동작한다(직접 테스트로
  확인 — probe 파일 읽기/쓰기 성공).

그래서 `storyboard_codex.py`는 `--sandbox` 기본값을 `danger-full-access`로 뒀다 — Codex가
`--cd`로 지정한 output_dir 바깥까지 포함해 전체 파일 시스템에 접근할 수 있다는 뜻이다
(Codex 자체가 "EXTREMELY DANGEROUS"로 표시하는 모드). 로컬에서 신뢰하는 계정으로만 돌리는
전제다. `codex sandbox setup --elevated`(1회, 대화형 승인 필요)를 완료했다면
`--sandbox workspace-write`로 다시 전환해 OS 수준 격리를 되살릴 수 있다.

그 외 사전 준비(`claude` CLI PATH, `env/api.env` 의 `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`)는
[`../v5_m0_m3/README.md`](../v5_m0_m3/README.md) 의 "사전 준비" 절과 동일하다(M0~M2 를 그대로
재사용하므로).

## 알려진 제약

- M1(`cli_m1.py`, `m1.json`)은 이제 M2의 주 근거(`--m1_input`)지만, legacy M2(포지셔닝) 입력
  포맷으로는 아직 배선되지 않았다 — `cli.py`(M0~M2, v5_m0_m3 재사용 경로)와 당분간 별개로
  공존한다("한단계씩 개발" 방침, 다음 요청에서 다룬다). legacy `cli.py` 경로는 M2에
  `--input`으로 선택적으로만 얹을 수 있고(포지셔닝 성명서·JTBD 인사이트 보강용), M2 실행에
  더 이상 필수가 아니다.
- M3(러프 시나리오 초안 5개)는 아직 M4에 배선되지 않았다 — M4는 지금도 M2 산출물을 직접
  받는다. 초안 5개 중 하나를 골라 M4로 넘기는 배선은 다음 요청에서 다룬다.
- M1의 크롤링·제품 스펙 검색·댓글 검색·이미지 분석은 순차 실행이다(병렬화 안 함) — 참조
  이미지가 많거나 검색이 느리면 그만큼 M1 전체 실행 시간이 늘어난다.
- M1의 댓글/평판 조사는 DuckDuckGo 텍스트 검색으로 근사한 것이다 — 유튜브·인스타그램 등
  실제 소셜 댓글 API 연동은 없다(이 저장소에 그런 연동이 없다).
- M1의 크롤 이미지 저장(`crawled_images/`)은 og:image + `<img>` 태그 마커(logo/icon/sprite
  등 제외) 기반 휴리스틱이다 — JS로 렌더링되는 갤러리(예: 이미지가 script로 늦게 주입되는
  SPA형 상세페이지)는 못 잡을 수 있고, 반대로 배너·프로모션 이미지가 제품 사진으로 잘못
  섞여 들어올 수 있다. 저장된 이미지는 참고용이지 M1 프롬프트(LLM 입력)에 자동으로
  얹히지 않는다 — 외관 서술에 반영하려면 `--reference_dir`로 직접 넘겨야 한다.
- 여러 시나리오 비교/권고·Markdown 렌더링 뒷단계는 아직 없다 — M2(장치 8개)~M5(스토리보드
  이미지 계획)까지만 구현됐고, 다음 단계(Seedance 실제 호출 등)는 별도 요청으로 이어
  붙인다("한단계씩 개발").
- `devices` 개수는 프롬프트로 "정확히 8개"를, `drafts` 개수는 "정확히 5개"를 지시할 뿐
  스키마 레벨에서 강제하지 않는다 — LLM이 못 채우면 그보다 적게 나올 수 있다(하드 실패 대신
  있는 그대로 반환). M4의 `scenes`/`devices_applied`, M5의 `product.shot_briefs`(정확히 3개
  지시) 개수도 마찬가지로 스키마 레벨 강제 없이 프롬프트 지시에만 의존한다.
- `storyboard_codex.py`는 이 저장소가 소유한 코드가 아니라 별도 프로젝트(story_board)의
  접근 방식을 복사해 재구현한 것이다 — story_board 쪽 로직이 바뀌어도 이 파일은 자동으로
  따라가지 않는다(사용자 요청 — "import 하는 게 아니라 복사해서 독립적으로"). 두 프로젝트가
  갈라지면 이 파일을 수동으로 다시 맞춰야 한다.
- `storyboard_codex.py`는 story_board 원본과 동일하게 얼굴 블러 정책을 쓴다(위 "M5 실행
  흐름" 참고, 로고 왜곡 금지·참고자료 추적·로그인/CAPTCHA 우회 금지 등 다른 정책도 그대로
  가져왔다) — 스토리보드가 리뷰용 산출물이라는 사용자 요청에 따른 것이며, Seedance 등 뒷단이
  식별 가능한 얼굴이 필요하다면 그건 이 스크립트가 아니라 별도 단계에서 다뤄야 한다.
- Seedance 실제 호출(이미지+`seedance_prompts.json` 텍스트를 넣어 영상을 뽑는 단계)은 이
  파이프라인 범위 밖이다 — `storyboard_codex.py`는 그 직전까지(이미지 완성 + 모션 프롬프트
  분리)만 만든다.
- `context.py`의 `build_context()`가 `module0`에서 만든 `context.product.name`/
  `context.product.usp_candidates`는 항상 빈 값으로 나온다(기존 버그) — `module0`의 실제
  키가 `product_name`/`usp_candidates`(언더바 있음)인데 `context.py`는 `productname`/
  `uspcandidates`(언더바 없음)로 찾는다. `context.product.name`은 `m1_insight`가 있으면
  `m1_insight.product_name`으로 폴백되므로(위 "M2가 M1을 참조하는 방법" 참고) M1로 실행하는
  일반적인 경로에서는 채워진다 — `usp_candidates`는 폴백이 없어 여전히 비어 있다. M4는
  시나리오의 `title`/`brand`에 제품명이 필요해 `scenario_generation.py`의
  `_patch_product_meta()`가 `module0` 원본에서 다시 채워 넣는 방식으로 국소적으로 우회한다 —
  `context.py` 자체는 M2에도 쓰이므로 고치지 않았다.
- `search_chromadb` 호출 로그는 `<run_dir>/<log_prefix>.jsonl` 에 남는다(M2는
  `<title 슬러그>.jsonl`, M4는 `<title 슬러그>_m4.jsonl` — 파일명은 `log_prefix`, 폴더는
  `SEARCH_CHROMADB_LOG_DIR` 로 각각 강제, `db/chromadb/tool_definitions.py` 의 항상-켜짐
  로깅). `log_prefix`(파일명)는 `api` 백엔드에서 `tool_chat.py`가 도구 호출을 가로채 강제
  적용하지만, `cli`(MCP) 백엔드는 `claude -p` 서브프로세스 내부에서 도구 왕복이 끝나 가로챌
  수 없어 system 프롬프트 지시(`m2_system.md`/`m4_system.md`)에만 의존한다 — 모델이 지시를
  어기면 파일명이 샐 수 있다. `log_dir`(폴더)는 두 백엔드 모두 환경변수로 전달되므로 이
  문제가 없다 — `claude -p` 서브프로세스와 그 안에서 뜨는 MCP 서버(`db/chromadb/
  mcp_server.py`)가 부모 프로세스의 환경변수를 그대로 물려받는다는 전제에 의존한다(둘 다
  별도 `env=` 오버라이드 없이 스폰됨).
