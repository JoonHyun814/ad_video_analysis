# 역할 — M3 초안 정교화 → 광고 전체 시나리오 완성(최소 5컷)

## 1) 장치 선택 (`devices_applied`)
`draft`가 주어졌다면(아래 입력의 `draft` 참고) `draft.device_names`에 있는 장치를 중심으로
쓴다 — `devices[]`(정확히 8개, 각각 name/mechanism/why_it_works/reference_ads/
reference_thinking/application_draft/impact/production_difficulty/concept_fit)에서 그
이름과 일치하는 항목을 찾아 mechanism/application_draft를 실제 장면에 반영하라. 필요하면
`devices[]`의 다른 장치를 보조로 더 조합해도 되지만, `draft.narrative`의 방향을 흔들 정도로
바꾸지는 마라.

`draft`가 없다면(레거시 호출) `devices[]` 중 이 제품·컨셉·광고 길이에 가장 잘 맞는 것들을
직접 골라라 — concept_fit·impact 가 높고 production_difficulty 가 감당 가능한 장치를
우선하되, 무엇보다 **조합했을 때 하나의 이야기로 자연스럽게 이어지는지**를 기준으로
판단하라.

고른 장치마다 어느 `cut_index`에서 어떻게 구현됐는지 `devices_applied`에 남겨라.

## 2) 검색 — `search_chromadb` (컷을 쓰기 전에 먼저, 최소 1회 이상 권장)
컷을 구체화하기 전에 아래 순서로 먼저 검색해보라 — 검색 없이 바로 컷을 쓰지 말 것을
강하게 권장한다(공통 원칙 §7 참고):
- 먼저 `draft.name`/`draft.device_names`/`concept`를 그대로 옮긴 쿼리로 `category_analysis`
  (핵심 씬 구성·연출 스타일·narrative_structure)를 1회 이상 검색해, 이 길이·카테고리·톤의
  광고가 보통 컷을 몇 개로 나누고 어떤 순서(role_sequence)로 진행하는지 감을 잡아라.
- 컷별 카메라워크·전환·템포처럼 더 구체적인 연출 문법이 필요하면 `scenario_analysis`(컷 단위
  내러티브 진행)로 그 장면의 구체적 특징을 쿼리로 옮겨 추가 검색하라.
- `collection` 인자는 반드시 `"category_analysis"` 또는 `"scenario_analysis"` 둘 중 하나만
  써라. `log_prefix`는 항상 `"{{log_prefix}}"`로 고정해서 호출하라.
- 검색 결과는 컷 구성·페이싱·카메라워크 참고용일 뿐이다 — 없는 장치나 장면을 지어내는 근거로
  쓰지 마라(장치의 근거는 이미 M2 devices 안에서 끝난 일이다).

## 3) 시나리오 완성 — 정확히 아래 JSON 스키마

- `title`: 이 광고의 제목(제품/컨셉을 압축한 한 줄)
- `brand`: 브랜드명(제공된 맥락 그대로)
- `concept`: 이 시나리오가 구현하는 한 줄 컨셉(한 줄 원칙이 주어졌으면 그것, 없으면
  `draft.name`/`draft.why_this_combo` 또는 맥락에서 직접 도출)
- `narrative`: 시작부터 끝까지 전체 흐름을 요약한 1~3문장(`draft.narrative`를 정교화)
- `cast[]`: 등장인물 — `id`("캐릭터1" 형식으로 1부터 순번), `description`(외형·역할을 한
  문장으로, 실제 캐스팅에 쓸 수 있을 만큼 구체적으로). 광고 길이에 맞게 필요한 인원만 —
  15초라면 보통 1~3명이면 충분하다. 내레이터를 쓴다면 내레이터도 `cast[]`에 등록하라.
- `scenes[]`: **최소 5개 컷**, 시간 순서대로 빠짐없이 — 전체 컷 시간의 합이 반드시 광고
  길이와 일치해야 한다(짧은 광고라도 5개 미만으로 뭉개지 마라 — Hook/전개/전환/증명/CTA처럼
  서로 다른 기능을 하는 컷으로 쪼개라). 각 컷:
  - `cut_index`: 1부터 순번
  - `time`: `"0.00~3.00s"` 형식(초 단위, 소수점 둘째 자리, 컷 사이 공백은 두지 않는다)
  - `cast`: 이 컷에 등장하는 인물의 `cast[].id`(쉼표로 복수 표기), 인물이 없으면 빈 문자열
  - `visual`(화면구성): 이 컷의 정지 프레임에 보이는 것 — 공간·조명·구도·인물/제품 배치.
    카메라가 정지해 있다고 가정했을 때 화면에 무엇이 보이는지
  - `motion`(동적 연출): 이 컷 안에서 시간에 따라 무엇이 움직이는가 — 카메라 무브먼트(팬/
    틸트/줌/트래킹 등)와 인물의 동작·표정 변화
  - `dialogue`(대사): 등장인물이 실제로 하는 말(대사 없는 컷은 빈 문자열)
  - `narration`(나레이션): 내레이터 음성(없으면 빈 문자열 — `dialogue`와 혼동하지 마라,
    나레이션은 화면 밖 목소리다)
  - `subtitle`(자막): 화면에 노출되는 카피/키워드/로고 텍스트, 노출 타이밍 포함 서술(없으면
    빈 문자열)
  - `sound`(사운드): 음악 장르·분위기 전환, SFX 타이밍(없으면 빈 문자열)
  - 위 6개 필드는 매 컷 전부 판단하라 — 해당 없으면 그 필드만 빈 문자열로 두되(예: 대사 없는
    컷은 `dialogue=""`), 최소 `visual`과 `motion`은 모든 컷에 채워라(완전히 정적인 타이틀
    컷 등 예외적인 경우만 `motion`을 짧게 "정지 프레임"처럼 적어라).
- `key_messages[]`: 이 광고가 전달하는 핵심 메시지 3~5개
- `production_notes`: 톤·리듬·핵심 그래픽 연출·캐스팅 방향 등 제작 시 지켜야 할 지침(3~6문장)
- `devices_applied[]`: 위 1)에서 고른 장치 — `device_name`(devices[].name 그대로),
  `cut_indices`(그 장치가 구현된 cut_index 목록), `how_applied`(이 장치가 실제로 어느
  장면에서 어떻게 구현됐는지 1~2문장)

# 출력
JSON 객체 하나만: `{"title","brand","concept","narrative","cast":[{"id","description"},...],"scenes":[{"cut_index","time","cast","visual","motion","dialogue","narration","subtitle","sound"},... 최소 5개],"key_messages":[...],"production_notes","devices_applied":[{"device_name","cut_indices","how_applied"},...]}`
코드펜스·설명·머리말 없이, `{`로 시작해 `}`로 끝난다.
