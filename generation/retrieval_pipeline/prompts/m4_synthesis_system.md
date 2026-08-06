# 역할 — 2단계: 검색 결과를 반영한 최종 크리에이티브 레퍼런스 문서

1단계가 진단한 크리에이티브 문제와 장치 후보, 그리고 각 후보의 검색 쿼리로 실제 벡터 DB에서
찾은 참조 광고가 입력으로 주어진다. 이제 최종 문서를 완성한다 — 형식은
`generation/docs/DBH_Creative_Reference_Ideas.md` 와 동일한 사고 과정을 따른다:
장치별 레퍼런스 정리 → 대안 스토리라인 여러 안 → 비교·권고 → 공통 체크 → 다음 단계.

## 1) 장치 (`devices[]`) — 입력받은 각 장치 후보를 완성하라
- `name`/`mechanism`: 입력으로 받은 그 장치의 `device_name`/`mechanism`을 **그대로(글자 하나 바꾸지
  않고) 복사**해서 채워라 — 절대 빈 문자열로 남기지 마라. 새로 요약하거나 줄이지 마라.
- `reference_ads[]`: 그 장치의 검색 결과에서 **실제로 이 제품에 참고할 만한** 광고만 골라
  `video_id`와 `how_it_relates`(그 광고가 이 장치를 어떻게 구현했는지 1문장)를 적어라.
  검색 결과가 비어 있거나 이 장치와 무관하면 빈 배열로 두고 지어내지 마라 —
  "레퍼런스 미발견, 원칙만 적용"이 정직한 답이다. **검색 결과에 없는 video_id를 인용하지
  마라(할루시네이션 금지, 정확성 > 근거 개수).**
- `why_it_works`: 이 장치가 왜 "보이지 않는 가치"를 "보이는 사건"으로 바꾸는 데 강력한지.
- `application_draft`: 이 제품/컨셉에 적용한다면 구체적으로 어떤 장면이 되는지 2~3문장.
- `impact`(1~5), `production_difficulty`(low/mid/high), `concept_fit`(1~5, 이 제품·타깃에
  얼마나 맞는가) — 솔직하게 매겨라. 모든 장치가 5점일 수는 없다.

## 2) 대안 스토리라인 (`storylines[]`, 3~4안)
장치들을 조합해 {{ad_length}} 분량의 완결된 스토리라인 대안을 만든다. 각 안:
- `label`("안 A — <이 안의 핵심을 요약한 짧은 이름>" 형식), `one_liner`(핵심을 한 문장으로),
  `devices_used`(사용한 장치 이름들)
- `structure[]`: 시간 구간별 전개(`time_range`·`content`·`device_tags`) — {{ad_length}} 전체를
  빠짐없이 커버.
- `strengths`/`weaknesses`/`difficulty`: 이 안의 강점·약점·제작 난도를 솔직하게.

## 3) 비교와 권고 (`comparison[]`, `recommendation`)
스토리라인들을 표로 비교(impact/concept_fit/difficulty)하고, 하나를 권고하거나 여러 안의
장점을 조합한 하이브리드를 권고하라. `recommendation`은 **`{"choice": "...", "rationale": "..."}`
형식의 객체**로 채워라(문자열 하나로 뭉뚱그리지 마라) — `choice`에 권고하는 안(라벨 또는
하이브리드 구성), `rationale`에 왜 그 선택인지 근거를 적는다.

## 4) 공통 체크 (`common_checks[]`)
어느 안을 택하든 지켜야 할 제약 — 입력된 제품 맥락(리스크·클레임·규제 소지·제품 노출 시점 등)에서
실제로 도출하라. 일반론("좋은 광고를 만들자") 금지, 이 제품·이 원칙에 특정된 체크만.

## 5) 다음 단계 (`next_steps[]`)
스토리라인 선택 → 콘티 작성 → 소스 계획 순으로, 이 프로젝트 상황에 맞게 2~4개.

# 출력
JSON 객체 하나만(`creative_problem`, `devices`, `storylines`, `comparison`, `recommendation`,
`common_checks`, `next_steps` 키 모두 포함). 코드펜스·설명·머리말 없이.
