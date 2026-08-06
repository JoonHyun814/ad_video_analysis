# generation/retrieval_pipeline 모듈

한 줄 크리에이티브 원칙(예: "기기를 보여주지 말고, 집에서 세계와 연결되는 순간을 보여라.")을
입력받아, **자사 광고 벡터 DB에서 실제로 검색한 참조 광고**를 근거로
[`../docs/DBH_Creative_Reference_Ideas.md`](../docs/DBH_Creative_Reference_Ideas.md) 와 같은
크리에이티브 레퍼런스 문서(연출 장치 → 대안 스토리라인 → 비교/권고 → 공통 체크 → 다음 단계)를
만드는 파이프라인이다.

## v5_m0_m3 와의 관계

- **M0~M2(소재 인제스트→인사이트→포지셔닝)는 v5_m0_m3 를 import 하지 않는 이 패키지 전용
  독립 구현이다**(사용자 요청 — "m0-m2 를 v5_m0_m3 거를 import 하는게 아니라 독립적으로 코드
  새롭게 만들어서"). v5_m0_m3 는 URL 크롤이 1차 소스이고 브랜드 가이드라인은 M1·M2 프롬프트에
  끼워 넣는 보조 지시였지만, 이 구현은 반대다 — **브랜드 가이드라인이 1차 소스**이고, 가이드라인
  에서 확인할 수 없는 정보만 크롤링으로 보완한다. 아래 "M0~M2 — 가이드라인 우선 독립 구현" 참고.
- **M3(컨셉 발산)는 이 패키지 전용으로 새로 구현했다** — v5_m0_m3 의 M3(렌즈 기반 다수 컨셉
  발산)와는 다른 방식으로, [`../docs/m3_concept.md`](../docs/m3_concept.md) 가 정리한 발산
  기법 7종(경험 은유/리프레이밍/디스럽션/환유·제유/JTBD/PAS/의인화) 각각으로 한 줄 컨셉을 만들고,
  타깃 그룹에 맞는 페르소나 3명이 각자 독립적으로 순위를 매긴 뒤 코드가 취합한다(LLM 5회,
  `concept_scout.py`). `cli_m4.py` 는 `--concept` 를 생략하면 이 중 취합 1위를 자동으로 쓰고,
  `--select_concept "<technique>"` 로 다른 후보를 지정할 수도 있다(v5_m0_m3 의 `cli_m4_m9.py`
  `--select_concept` 와 같은 패턴). **이 파이프라인의 실행 폴더(`<날짜>_<제목>/`)도 M3부터
  만들어진다** — M4가 아니라 M3가 `--title` 을 받는다.
- **M4~M7(레퍼런스 기반 연출 아이디어)은 이 패키지에서 새로 설계한 단계**다. v5_m0_m3 의
  M4(약한 컨셉 킬)와 이름만 같을 뿐 역할이 다르다 — 컨셉을 평가·킬하는 게 아니라, 눈에 보이지
  않는 원칙을 "보이는 사건"으로 번역할 연출 장치를 레퍼런스와 함께 제안한다.
- LLM 호출 인프라(`chat_json` — claude -p CLI/Anthropic API 선택)는 `generation.v5_m0_m3.llm_adapter`
  를 그대로 재사용한다. 다만 이 파이프라인은 M3/M4~M9 처럼 **LLM이 tool_use 로 검색 여부를
  스스로 판단**하게 하지 않는다 — 아래 "왜 검색을 코드가 직접 실행하는가" 참고.

## M0~M2 — 가이드라인 우선 독립 구현

브랜드 가이드라인(txt/md, `--guideline`, 필수)이 1차 소스이고, 제품 URL(`--url`, 선택)은
가이드라인이 다루지 않는 정보를 보완하는 2차 소스다.

```
M0 module0    (LLM 1회, --url 지정 시 크롤 1회 선행)         module0.py
    브랜드 가이드라인(1차) + 제품 페이지 크롤 결과(2차, 있으면)
    → product_name/brand/category/usp_candidates/facts/target_hints/tone + ingest_note
    (가이드라인·크롤 중 어느 쪽에서 왔는지 매 필드에 태깅)

M1 module1    (LLM 1회)                                       module1.py
    M0 → core_job/human_truth/human_truth_contradiction/target_label

M2 module2    (LLM 1회)                                       module2.py
    M0 + M1 → positioning_statement/value_proposition/unique_attributes
```

`product_image_url` 은 LLM에게 맡기지 않는다 — `crawler.py`(httpx+BeautifulSoup, v5_m0_m3 를
참조하지 않는 독립 구현)가 크롤한 페이지의 `og:image`/`twitter:image`/첫 `<img>` 중 하나를 코드가
결정적으로 골라 채운다. 존재하지 않는 이미지 경로를 LLM이 지어낼 위험을 원천 차단하기 위해서다
— 이 파이프라인 전반의 원칙("코드로 결정적으로 구할 수 있는 값은 코드가 채우고, LLM은 판단이
필요한 것만 한다")과 같은 이유다.

`--url` 을 생략하면 M0는 가이드라인만으로 채울 수 있는 만큼만 채우고, 나머지는 빈 값으로
남긴다(하드 실패하지 않음) — `ingest_note` 에 그 사실이 남는다. 크롤이 실패해도(차단·타임아웃
등) 마찬가지로 graceful 하게 빈 크롤 텍스트로 처리하고 `module0.crawl_error` 에 이유를 남긴다.

## M3 — 발산 기법 7종 컨셉 생성 → 페르소나 3명이 순위 매김 → 취합

M3는 한 번의 LLM 호출로 끝나지 않는다. "컨셉 순위를 매길 때 target 그룹에 맞는 페르소나를 만들어
각자 순위를 매기게 한 뒤 취합하라"는 사용자 요청에 따라 `concept_scout.py` 가 네 단계를
순서대로 실행한다(LLM 호출 총 5회):

```
1) run_candidates()      LLM 1회 — m3_concept.md 발산 기법 7종 → 컨셉 후보 7개(아직 순위 없음)
2) run_personas()        LLM 1회 — M0~M2 타깃 정의 안에서 서로 다른 페르소나 3명 생성
3) run_persona_ranking() LLM 1회 × 3(페르소나마다) — "서브 에이전트": 각 호출은 그 페르소나
   하나의 시점만 가지고(다른 페르소나의 존재를 모른 채) 7개 컨셉 전부에 독립적으로 순위를 매긴다
4) _aggregate()          코드, 결정적(LLM 아님) — 3명의 rank/score 를 평균해 최종 순위를 정한다
```

★ "서브 에이전트"는 Claude Code 의 Agent 툴이 아니라, `generation.v5_m0_m3.llm_adapter` 를 통한
독립적인 LLM 호출로 구현했다 — 이 파이프라인은 M4~M7 도 전부 같은 방식(무상태·독립 LLM 호출)을
쓰므로 인프라를 통일했다. 4단계 취합은 M5(retrieval.py)가 "검색 실행은 코드가 결정적으로
한다"는 원칙과 같은 이유로 LLM 이 아니라 코드가 한다 — 평균 순위 오름차순(동점이면 평균 점수
내림차순)이라는 규칙이 고정돼 있어 같은 입력이면 항상 같은 결과가 나온다.

모든 컨셉은 M4~M7이 그대로 이어받을 수 있도록 "~을 보여주지 말고, ~을 보여줘라" 형식으로
나온다 — DBH_Creative_Reference_Ideas.md 예시와 같은 형식이다.

`cli_m3.py` 실행 결과(`<날짜>_<제목>/m3.json`)의 `m3.personas[]` 는 페르소나 3명(`name`/
`profile`/`priorities`/`grounding`), `m3.concepts[]` 는 컨셉 7개를 담는다 — 각 항목은
`technique`(기법명), `concept_line`(한 줄 컨셉), `grounding`(M0~M2 근거), `persona_ranks`(페르소나별
원본 순위·점수·평가 배열), `aggregate_rank`(1~7, 최종 순위, 동점 없음), `average_rank`/
`average_score`(참고용 평균값)를 담는다. `cli_m4.py` 가 이 배열을 읽어 컨셉을 고른다 — 아래
"사용법" 참고.

## M4~M7 — 검색기준 축 기반 재설계

M4~M7 은 [`../docs/검색기준.txt`](../docs/검색기준.txt) 와
[`../docs/검색기준2.txt`](../docs/검색기준2.txt) 가 정리한 실무 방식을 반영해 설계했다 —
현업 감독·촬영감독은 "이 광고 비슷한 거" 하나로 뭉뚱그려 레퍼런스를 찾지 않고, **지금 무엇이
안 풀리는가에 따라 검색 축을 나눠서** 따로 찾는다. 이 파이프라인이 쓰는 세 축:

| 축(`axis`) | 무엇을 찾는가 |
|---|---|
| `narrative_form`(구조) | 이 메시지를 어떤 서사 뼈대로 풀지 — 문제→해결, 비네트 나열, 대조, 원샷, 일상 몽타주, 은유적 세계관, 데모형 등 |
| `tone_mood`(톤·무드) | 온도를 맞추기 위한 것 — 조명 룩, 캐스팅 인상, 컬러 절제, 연기 톤 (첫 3초 인상으로 판단) |
| `shot_technique`(샷·기술) | 이걸 어떻게 찍을지 — 인서트·구도·컷 리듬·카메라 무브먼트 (영상 전체가 아니라 초 단위 구간) |

이 축을 따라 4단계로 나눴다(사용자 요청 — "m4: 검색기준 문서를 참조하여 쿼리 생성",
"m5: 쿼리 실행 및 결과 기록", "m6: 쿼리별 장치 생성", "m7: m6 들을 조립해서 스토리라인 생성"):

```
M4 query_scout      (LLM 호출 1회, 아직 검색 없음)                cli_m4.py
    한 줄 원칙 + M0~M2 맥락
    → 크리에이티브 문제 진단 + 축(구조/톤무드/샷기술)별 검색 쿼리 5~8개 제안

M5 retrieval          (코드, 결정적 — LLM 아님)                    cli_m5.py
    evaluation.creative.reference_retrieval.search_production_reference /
    search_concept_reference 를 쿼리마다 1회씩 그대로 호출(evaluation/ad_concept_production 이
    output/vector_db 에 적재한 ad_production_reference / ad_concept_reference 컬렉션)

M6 device_synthesis     (LLM 호출 1회, 검색 결과 반영)              cli_m6.py
    쿼리 1건당 연출 장치 1개를 생성 — 각 장치는 자신의 쿼리가 찾아온 검색 결과에만 근거한다
    (다른 쿼리의 결과를 섞어 쓰지 않는다)

M7 storyline             (LLM 호출 1회 이상)                       cli_m7.py
    장치들을 조합해 대안 스토리라인 + 비교/권고 + 공통 체크 + 다음 단계를 만들고,
    Markdown 문서로 렌더링(코드)한다. 매 호출마다 LLM 이 스스로 "지금 가진 장치로 충분한가"를
    진단(gap_assessment)하고, 부족하면 추가 쿼리를 제안한다 — 아래 "M7 자동 재검색 루프" 참고.
```

각 단계는 바로 앞 단계가 저장한 JSON 파일을 `--input` 으로만 받는다 — 중간 산출물을 다시
계산하지 않고 파일에서 그대로 이어받는다.

### 왜 검색(M5)을 코드가 직접 실행하는가

v5_m0_m3 의 `--retrieval` 은 LLM에게 검색 도구(MCP/tool_use)를 쥐어주고 "쓸지 말지, 몇 건을
볼지"까지 LLM이 그때그때 판단하게 한다 — 그 결과 실제로 어떤 쿼리가 몇 번 나갔는지는 JSONL
로그를 봐야만 알 수 있고, "모델에 최종적으로 어떤 텍스트가 들어갔는지"는 별도로 재구성해야
한다. 이 파이프라인은 사용자 요청으로 **검색 실행 자체를 코드가 결정적으로 수행**하도록
뒤집었다 — 그래서 아래 세 가지가 항상 파일로 그대로 남는다:

1. **서칭에 입력되는 쿼리** — M4가 제안한 검색어 그대로(`m4.json` → M5가 `search_queries` 로 재확인)
2. **서칭 결과로 나온 데이터** — 벡터 DB가 실제로 반환한 원본(`m5.json` 의 `search_results`/`searches`)
3. **실제 모델에 입력되는 데이터** — 검색 결과를 반영해 M6·M7이 실제로 보낸 system/user 프롬프트
   원문 그대로(`m4.json`/`m6.json` 의 `prompt` 키, `m7.json` 의 `storyline_prompt` 키)

### M7 자동 재검색 루프

M7은 스토리라인을 조립할 때마다 스스로 "지금 가진 장치만으로 설득력 있는 안을 만들 수 있는가"를
자가진단한다(`gap_assessment`). 부족하다고 판단하면(`sufficient: false`) 무엇이 부족한지
(`note`)와 그 공백을 메울 추가 쿼리(`additional_queries`, M4와 같은 스키마)를 함께 낸다.

`pipeline.run_m7()` 은 이 필드를 읽어 **새 M4 진단을 다시 하지 않고** `additional_queries`를
그대로 M5(검색 실행)→M6(장치 생성)에 넣어 장치를 보강한 뒤, M7을 다시 호출한다 — M7 자신이
이미 무엇이 부족한지 정확히 알고 있으므로 그 판단을 그대로 다음 라운드의 쿼리로 쓰는 것이
새로 진단하는 것보다 정확하다. `--max_rounds`(기본 2 — 최초 1회 + 재시도 1회)를 넘기면 그
시점의 결과로 확정한다. 재시도로 생긴 라운드는 `m5_r2.json`/`m6_r2.json` 같은 파일로 그대로
남는다(투명성 유지 — 무엇을 더 검색했고 무엇이 나왔는지 항상 파일로 확인 가능).

## 코드와 프롬프트 분리

시스템/유저 프롬프트 문구는 전부 `prompts/*.md` 에 있고, 코드는 `{{변수}}` 채우기(`prompt_loader.py`)와
LLM 호출·파싱만 한다 — 실제로 모델에 무엇이 어떤 순서로 들어가는지 `.py` 를 안 읽고 `.md` 만 봐도
알 수 있다.

| 프롬프트 파일 | 역할 | 채워지는 변수 |
|------|------|------|
| `prompts/m0_system.md` | M0 지시문 — 가이드라인 우선 제품 정보 확보 | (없음) |
| `prompts/m0_user.md` | M0 입력 | `guideline_text`, `crawl_title`, `crawl_text` |
| `prompts/m1_system.md` | M1 지시문 — 핵심 인사이트 도출 | (없음) |
| `prompts/m1_user.md` | M1 입력 | `module0_json` |
| `prompts/m2_system.md` | M2 지시문 — 포지셔닝 수립 | (없음) |
| `prompts/m2_user.md` | M2 입력 | `module0_json`, `module1_json` |
| `prompts/m3_concepts_system.md` | M3 1단계 지시문 — 발산 기법 7종 컨셉 생성(순위 없음) | (없음) |
| `prompts/m3_concepts_user.md` | M3 1단계 입력 | `context_json` |
| `prompts/m3_personas_system.md` | M3 2단계 지시문 — 타깃 그룹 페르소나 3명 생성 | (없음) |
| `prompts/m3_personas_user.md` | M3 2단계 입력 | `context_json` |
| `prompts/m3_persona_rank_system.md` | M3 3단계 지시문 — 페르소나 1명 시점으로 컨셉 7개 순위(서브 에이전트, 페르소나마다 재사용) | (없음) |
| `prompts/m3_persona_rank_user.md` | M3 3단계 입력 | `persona_json`, `context_json`, `concepts_json` |
| `prompts/common.md` | M4·M6·M7 세 LLM 호출이 공유하는 페르소나(레퍼런스 리서치 디렉터) | (없음) |
| `prompts/query_scout_system.md` | M4 지시문 — 문제 진단 + 축별 검색 쿼리 제안 | (없음) |
| `prompts/query_scout_user.md` | M4 입력 | `concept_line`, `ad_length`, `context_json` |
| `prompts/device_synthesis_system.md` | M6 지시문 — 쿼리별 장치 완성 | (없음) |
| `prompts/device_synthesis_user.md` | M6 입력 | `concept_line`, `ad_length`, `context_json`, `creative_problem`, `queries_with_search_results_json` |
| `prompts/storyline_system.md` | M7 지시문 — 스토리라인 조립 + 자가진단 | (없음) |
| `prompts/storyline_user.md` | M7 입력 | `concept_line`, `ad_length`, `context_json`, `creative_problem`, `devices_json` |

## 파일 구성

| 파일 | 역할 |
|------|------|
| `cli.py` | M0~M2 진입점(`--guideline`(필수) `--url`(선택) `--llm_backend`) |
| `cli_m3.py` | M3 진입점(`--input <m0_m2.json>` `--title` `--llm_backend` — 실행 폴더를 새로 만드는 단계) |
| `cli_m4.py` | M4 진입점(`--input <m3.json>` `[--concept \| --select_concept]` `--llm_backend`) |
| `cli_m5.py` | M5 진입점(`--input <m4.json>` `--top_k` `--db_path`, LLM 호출 없음) |
| `cli_m6.py` | M6 진입점(`--input <m5.json>` `--llm_backend`) |
| `cli_m7.py` | M7 진입점(`--input <m6.json>` `--llm_backend` `--top_k` `--db_path` `--max_rounds` `--output`) |
| `pipeline.py` | `run_m0_m2()` / `run_m3()` / `run_m4()`~`run_m7()`(자동 재검색 루프 포함) / `run_m3_m7()`(편의 래퍼) 오케스트레이션 |
| `crawler.py` | M0 부속 — URL 페이지 텍스트·대표 이미지 추출(httpx+BeautifulSoup, 결정적, LLM 아님) |
| `module0.py` | M0 — LLM 호출, 가이드라인 우선 제품 정보 확보 + 크롤 보완 |
| `module1.py` | M1 — LLM 호출, 핵심 인사이트(core job/human truth/타깃) 도출 |
| `module2.py` | M2 — LLM 호출, 포지셔닝 수립 |
| `module_schemas.py` | `Module0LLM`/`Module1`/`Module2`/`USPCandidate` 등 M0~M2 전용 pydantic 모델 |
| `context.py` | module0/m1/m2 → 압축 맥락(`build_context`) — M3에서 한 번만 만들어져 이후 `context` 로만 전달됨 |
| `concept_scout.py` | M3 — LLM 호출 5회(컨셉 후보/페르소나/페르소나별 순위 ×3) + 코드 취합 |
| `query_scout.py` | M4 — LLM 호출, 문제 진단 + 축별 검색 쿼리 제안 |
| `retrieval.py` | M5 — 결정적 검색 실행, `evaluation.creative.reference_retrieval` 직접 호출(도구 호출 아님) |
| `device_synthesis.py` | M6 — LLM 호출, 쿼리 1건당 장치 1개 생성 |
| `storyline.py` | M7 — LLM 호출, 장치 조립 + 자가진단(gap_assessment) |
| `render_markdown.py` | M7 부속 — 장치 목록 + 스토리라인 출력 → DBH 문서 형식 Markdown 렌더링(LLM 아님) |
| `prompt_loader.py` | `prompts/*.md` 로더 + `{{변수}}` 치환(md_parser.py 와 같은 방식, 이 패키지 전용) |
| `schemas.py` | `ConceptCandidate`/`Persona`/`PersonaConceptRank`/`RankedConcept`/`M3Output`/`SearchQuery`/`M4Output`/`QueryDevice`/`M6Output`/`GapAssessment`/`StorylineOutput` 등 pydantic 모델 |
| `prompts/` | 위 표 참고 |

## 사용법

```bash
# 1) M0~M2 (가이드라인이 1차 소스, --url 은 보완용 선택)
python -m generation.retrieval_pipeline.cli \
    --guideline <가이드라인.md|txt> \
    [--url <제품 상세페이지 URL>] [--llm_backend cli|api] [--output_dir output/retrieval_pipeline]

# 2) M3 (발산 기법 7종 컨셉 생성 + 페르소나 3명 순위 취합 — 여기서 <날짜>_<제목>/ 실행 폴더가 새로 생긴다)
python -m generation.retrieval_pipeline.cli_m3 \
    --input output/retrieval_pipeline/<slug>_m0_m2.json \
    --title "DBH_15초_CTV" \
    [--llm_backend cli|api]

# 3) M4 (--concept/--select_concept 를 모두 생략하면 M3 취합 1위 컨셉을 자동으로 쓴다)
python -m generation.retrieval_pipeline.cli_m4 \
    --input output/retrieval_pipeline/<날짜>_<제목>/m3.json \
    [--concept "기기를 보여주지 말고, 집에서 세계와 연결되는 순간을 보여라." | --select_concept "PAS 모델"] \
    [--ad_length 15초] [--llm_backend cli|api]

# 4) M5 (쿼리별 벡터 DB 검색 실행 — M4를 다시 태우지 않고 재검색하고 싶으면 이 단계만 재실행)
python -m generation.retrieval_pipeline.cli_m5 \
    --input output/retrieval_pipeline/<날짜>_<제목>/m4.json \
    [--top_k 3] [--db_path output/vector_db]

# 5) M6 (쿼리별 장치 생성)
python -m generation.retrieval_pipeline.cli_m6 \
    --input output/retrieval_pipeline/<날짜>_<제목>/m5.json \
    [--llm_backend cli|api]

# 6) M7 (장치 조립 → 스토리라인 생성 + 필요시 자동 재검색 → 최종 Markdown 렌더링)
python -m generation.retrieval_pipeline.cli_m7 \
    --input output/retrieval_pipeline/<날짜>_<제목>/m6.json \
    [--llm_backend cli|api] [--top_k 3] [--db_path output/vector_db] [--max_rounds 2]
```

M5~M7 은 `--output_dir`/`--output` 을 생략하면 각각의 `--input` 파일과 같은 디렉터리에 이어서
저장한다 — `--title`/날짜 로직을 반복할 필요 없이 한 실행 폴더 안에 체인이 이어진다.

### 옵션

| 옵션 | 있는 CLI | 기본값 | 설명 |
|------|----------|--------|------|
| `--input` | `cli_m3`~`cli_m7` | (필수) | 바로 앞 단계가 저장한 JSON 경로 |
| `--title` | `cli_m3` | (필수) | 실행 폴더명에 쓸 프로젝트 제목(슬러그화) |
| `--concept` | `cli_m4` | `""` | 한 줄 크리에이티브 원칙 직접 지정(우선순위 최상 — 지정 시 M3 결과 무시) |
| `--select_concept` | `cli_m4` | `""` | M3 `concepts[]` 중 이 `technique` 명과 일치하는 후보 사용(`--concept` 없을 때만) |
| `--ad_length` | `cli_m4` | `15초` | 스토리라인 길이 |
| `--top_k` | `cli_m5`, `cli_m7` | `3` | 쿼리 1개당 검색해올 참조 광고 수(최대 20, `reference_retrieval._MAX_TOP_K`) — `cli_m7`은 자동 재검색 라운드에만 쓰인다 |
| `--db_path` | `cli_m5`, `cli_m7` | `output/vector_db` | `evaluation/ad_concept_production` 이 적재한 ChromaDB 경로 |
| `--max_rounds` | `cli_m7` | `2` | M7 자가진단이 부족하다고 판단할 때 자동 재검색을 허용할 최대 라운드 수(1이면 재시도 없음) |
| `--llm_backend` | `cli`, `cli_m3`, `cli_m4`, `cli_m6`, `cli_m7` | `cli` | `cli`(claude -p) \| `api`(Anthropic API, `env/api.env` `ANTHROPIC_API_KEY`) |
| `--output_dir` | `cli`, `cli_m3`, `cli_m4`, `cli_m5`, `cli_m6` | `cli`/`cli_m3`: `output/retrieval_pipeline`, 나머지: `--input` 과 같은 디렉터리 | 결과 저장 경로 |
| `--output` | `cli_m7` | `--input` 과 같은 디렉터리의 `creative_reference_ideas.md` | 최종 Markdown 저장 경로 |
| `--guideline` | `cli` | (필수) | 브랜드 가이드라인 md/txt 경로 — M0의 1차 소스 |
| `--url` | `cli` | `""` | 제품 상세페이지 URL(선택) — 가이드라인에 없는 정보(제품 이미지 등)를 크롤로 보완 |

`cli_m5.py` 는 LLM을 호출하지 않으므로 `--llm_backend` 가 없다. `cli_m4`에서 `--concept`도
`--select_concept`도 없는데 입력 파일의 `m3.concepts`가 비어 있으면(M3를 아직 실행하지 않은
경우) 에러로 종료한다.

## 출력 구조

`--title "DBH_15초_CTV"` 로 오늘(예: 2026-08-06) M3를 실행하면 그 아래 M4~M7 이 이어서 저장한다:

```
output/retrieval_pipeline/
├── <guideline 파일명>_m0_m2.json       M0~M2 산출물(cli.py) — module0/m1/m2 + prompts + crawl
└── 20260806_DBH_15초_CTV/             cli_m3.py 가 새로 만드는 실행 폴더
    ├── m3.json                        M3 산출물 — context(압축 요약) + m3.personas[3] + m3.concepts[7](취합 순위)
    ├── m4.json                        M4 산출물 — prompt(실제 모델 입력) + creative_problem + queries(축별)
    ├── m5.json                        M5 산출물 — search_queries(입력 쿼리) + search_results(원본 응답) + searches
    ├── m6.json                        M6 산출물 — prompt(실제 모델 입력, 검색결과 반영) + devices(쿼리별 장치)
    ├── m5_r2.json, m6_r2.json         (선택) M7 자동 재검색 라운드 산출물 — gap_note + 추가 쿼리/결과/장치
    ├── m7.json                        M7 최종 산출물 — storylines/comparison/recommendation/common_checks/next_steps/gap_assessment/rounds
    └── creative_reference_ideas.md    최종 문서(DBH 문서 형식) — 사람이 읽는 산출물
```

module0/m1/m2 원본은 `<slug>_m0_m2.json` 에만 있고, M3가 여기서 뽑아낸 `context`(압축 요약)만
m3.json 부터 m7.json 까지 계속 실려 다닌다 — module0/m1/m2 자체를 모든 산출물에 중복해서 담지
않는다(사용자 요청).

`m3.json` 의 `m3.prompts` 키(컨셉/페르소나/페르소나별 순위 프롬프트 전부), `m4.json`/`m6.json`
각각의 `prompt` 키, `m7.json` 의 `storyline_prompt` 키에 그 단계가 실제로 LLM에 보낸
system/user 원문이 그대로 남는다 — "실제 모델에 입력되는 데이터"를 확인하려면 이 파일들만
보면 된다.

## 사전 준비

M5(검색)가 파이프라인에 항상 포함되므로, `output/vector_db` 에 두 컬렉션이 이미 적재돼 있어야 한다:

```bash
python -m evaluation.cli --mode strategy --video_id <ID> --data_dir <dir>
python -m evaluation.cli --mode ad_concept_production --video_id <ID> --data_dir <dir>
```

(`evaluation/ad_concept_production/README.md` 참고 — `ad_concept_reference`/`ad_production_reference`
두 컬렉션에 동시 적재된다.) 컬렉션이 비어 있으면 검색 결과가 항상 0건으로 나오고, M6은
"레퍼런스 미발견 — 원칙만 적용"으로 devices 를 채운다(하드 실패하지 않음).

LLM 호출은 `generation.v5_m0_m3.llm_adapter` 를 그대로 재사용하므로(M0~M7 전 단계 공통),
`--llm_backend cli` 를 쓰려면 `claude` CLI가 PATH 에 있어야 하고, `--llm_backend api` 를 쓰려면
`env/api.env` 의 `ANTHROPIC_API_KEY` 가 있어야 한다. `crawler.py`(M0)는 `httpx`/`beautifulsoup4`
패키지가 필요하다(이미 v5_m0_m3 가 같은 패키지를 쓰므로 보통 이미 설치돼 있다).

## 알려진 제약

- M0의 크롤(`crawler.py`)은 v5_m0_m3/v1_bridge.py 와 달리 curl_cffi 폴백·MCP 브라우저 크롤러
  같은 봇 차단 우회 체인이 없다(httpx 단발 요청만) — 크롤이 차단되면 그냥 빈 값으로 두고
  가이드라인만으로 M0를 채운다(하드 실패하지 않지만, `--url` 이 있어도 실제로는 못 쓸 수 있다).
- `product_image_url` 은 `og:image`/`twitter:image`/첫 `<img>` 순으로 코드가 고른 것이라, 페이지
  구조에 따라 제품과 무관한 이미지(로고 등)가 잡힐 수 있다 — 다트비트 테스트에서도 대표 이미지가
  없어 로고 이미지가 잡혔다. 필요하면 M0 실행 후 `module0.product_image_url` 을 수동으로 고친다.
- M3는 v5_m0_m3 M3(렌즈 기반 다수 발산·GATE 재평가)와 달리, 정확히 7개(발산 기법당 1개)만
  만들고 재발산 루프가 없다 — 7개 모두 마음에 안 들면 `cli_m3`를 다시 실행해 새로 뽑는 수밖에
  없다.
- M3의 페르소나 3명은 매 실행마다 새로 만들어진다(고정 페르소나 목록을 재사용하지 않음) — 같은
  제품이라도 `cli_m3`를 다시 실행하면 페르소나 구성과 그에 따른 순위가 달라질 수 있다.
- M3는 LLM 호출을 5회(컨셉 후보 1 + 페르소나 1 + 페르소나별 순위 3) 쓴다 — M4~M7의 개별 LLM
  호출(각 1회 이상)보다 비용이 크다는 점을 감안한다.
- `retrieval.py`(M5) 는 쿼리 1건당 검색 1건만 실행한다(v5_m0_m3 M3 의 `_scout_emergent_lenses`
  처럼 "부족하면 재검색" 루프는 M5 자체엔 없음 — 대신 M7 이 자가진단으로 그 역할을 대체한다).
- `segment_column`/`segment_value` 필터는 쓰지 않는다(자연어 `query_text` 검색만) — enum 값을
  틀리게 추측해 결과 0건이 되는 실패를 피하기 위한 의도적 단순화다(`evaluation/creative/reference_retrieval.py`
  자체도 "확신 없으면 query_text만 써라"라고 안내한다).
- `module0.py`(M0)/`module1.py`(M1)/`module2.py`(M2)/`concept_scout.py`(M3)/`query_scout.py`(M4)/
  `device_synthesis.py`(M6)/`storyline.py`(M7) 는 `llm_adapter.chat_json()` 이 `{"error": ...}`
  를 반환하면 즉시 `RuntimeError` 를 던진다 —
  pydantic 의 기본 결측 필드 처리(빈 문자열/빈 배열)가 LLM 호출 실패를 "결과 0개짜리 정상
  결과"로 조용히 둔갑시키는 것을 막기 위해서다. 실행이 실패하면 에러 메시지를 보고 해당
  단계만 재실행하면 된다(앞 단계 파일은 그대로 남아 있다).
- M7 자동 재검색 루프는 라운드마다 M6(LLM 호출)을 다시 태운다 — `--max_rounds` 를 과도하게
  키우면 비용이 그만큼 커진다. 기본값 2(최초 1회 + 재시도 1회)면 대부분 충분하다.
