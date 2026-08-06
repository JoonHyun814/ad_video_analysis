# generation/retrieval_pipeline 모듈

한 줄 크리에이티브 원칙(예: "기기를 보여주지 말고, 집에서 세계와 연결되는 순간을 보여라.")을
입력받아, **자사 광고 벡터 DB에서 실제로 검색한 참조 광고**를 근거로
[`../docs/DBH_Creative_Reference_Ideas.md`](../docs/DBH_Creative_Reference_Ideas.md) 와 같은
크리에이티브 레퍼런스 문서(연출 장치 → 대안 스토리라인 → 비교/권고 → 공통 체크 → 다음 단계)를
만드는 파이프라인이다.

## v5_m0_m3 와의 관계

- **M0~M2(소재 인제스트→인사이트→포지셔닝)는 `generation/v5_m0_m3` 와 완전히 동일한 로직을
  그대로 재사용한다** — `cli.py` 는 `generation.v5_m0_m3.pipeline.run_m0_m2()` 를 그대로
  호출할 뿐, M0~M2 를 이 패키지 안에 다시 구현하지 않는다.
- **M3(컨셉 발산)는 아직 설계 전이라 공백 placeholder다** — `cli_m3.py` 는 LLM 호출 없이
  `{"module0","m1","m2","m3":{"note": "..."}}` 계약 형태만 맞춰 다음 단계로 넘긴다. 나중에
  M3 를 채우더라도 `cli_m4.py` 의 입력 형식(`<slug>_m0_m3.json`)은 바뀌지 않는다.
  ★따라서 `--select_concept`처럼 M3 산출물에 의존하는 기능은 아직 없다 — M4 는 M3 의
  `concepts[]`가 아니라 **사용자가 직접 입력한 한 줄 원칙**을 받는다.
- **M4~M7(레퍼런스 기반 연출 아이디어)은 이 패키지에서 새로 설계한 단계**다. v5_m0_m3 의
  M4(약한 컨셉 킬)와 이름만 같을 뿐 역할이 다르다 — 컨셉을 평가·킬하는 게 아니라, 눈에 보이지
  않는 원칙을 "보이는 사건"으로 번역할 연출 장치를 레퍼런스와 함께 제안한다.
- LLM 호출 인프라(`chat_json` — claude -p CLI/Anthropic API 선택)는 `generation.v5_m0_m3.llm_adapter`
  를 그대로 재사용한다. 다만 이 파이프라인은 M3/M4~M9 처럼 **LLM이 tool_use 로 검색 여부를
  스스로 판단**하게 하지 않는다 — 아래 "왜 검색을 코드가 직접 실행하는가" 참고.

## M4~M7 — 단계별 독립 CLI로 분리한 이유

v5_m0_m3 는 `cli.py`(M0~M2) / `cli_m3.py`(M3) / `cli_m4_m9.py`(M4~M9) 로 나눠, 비용이 큰
LLM 호출 단계를 고정해두고 뒷 단계만 몇 번이든 다시 돌릴 수 있게 한다. 이 파이프라인도 같은
이유로 옛 단일 `cli_m4.py`(문제 진단→검색→합성→렌더링을 한 번에 실행)를 **M4/M5/M6/M7 네 개의
독립 CLI**로 쪼갰다 — 예를 들어 검색 결과가 부실해 `--top_k` 만 올려 다시 검색하고 싶을 때
M4(문제 진단, LLM 호출)를 다시 태우지 않고 M5만 재실행할 수 있다.

```
M4 device_scout   (LLM 호출 1회, 아직 검색 없음)                cli_m4.py
    한 줄 원칙 + M0~M2 맥락
    → 크리에이티브 문제 진단 + 연출 장치 후보 + 장치별 검색 쿼리 제안

M5 retrieval       (코드, 결정적 — LLM 아님)                     cli_m5.py
    evaluation.creative.reference_retrieval.search_production_reference /
    search_concept_reference 를 장치마다 1회씩 그대로 호출(evaluation/ad_concept_production 이
    output/vector_db 에 적재한 ad_production_reference / ad_concept_reference 컬렉션)

M6 synthesis       (LLM 호출 1회, 검색 결과 반영)                cli_m6.py
    한 줄 원칙 + M0~M2 맥락 + 크리에이티브 문제 + (장치, 실제 검색 결과)
    → 장치별 레퍼런스 인용 + 대안 스토리라인 + 비교표 + 권고 + 공통 체크 + 다음 단계

M7 render_markdown (코드, LLM 아님)                               cli_m7.py
    M6의 구조화 출력 → DBH_Creative_Reference_Ideas.md 형식 Markdown 문서로 렌더링
```

각 단계는 바로 앞 단계가 저장한 JSON 파일을 `--input` 으로만 받는다 — 중간 산출물을 다시
계산하지 않고 파일에서 그대로 이어받는다.

### 왜 검색(M5)을 코드가 직접 실행하는가

v5_m0_m3 의 `--retrieval` 은 LLM에게 검색 도구(MCP/tool_use)를 쥐어주고 "쓸지 말지, 몇 건을
볼지"까지 LLM이 그때그때 판단하게 한다 — 그 결과 실제로 어떤 쿼리가 몇 번 나갔는지는 JSONL
로그(`<slug>_retrieval.jsonl`)를 봐야만 알 수 있고, "모델에 최종적으로 어떤 텍스트가 들어갔는지"는
별도로 재구성해야 한다. 이 파이프라인은 사용자 요청으로 **검색 실행 자체를 코드가 결정적으로
수행**하도록 뒤집었다 — 그래서 아래 세 가지가 항상 파일로 그대로 남는다:

1. **서칭에 입력되는 쿼리** — M4가 제안한 검색어 그대로(`m4.json` → M5가 `search_queries` 로 재확인)
2. **서칭 결과로 나온 데이터** — 벡터 DB가 실제로 반환한 원본(`m5.json` 의 `search_results`/`searches`)
3. **실제 모델에 입력되는 데이터** — 검색 결과를 반영해 M6이 실제로 보낸 system/user 프롬프트
   원문 그대로(`m4.json`/`m6.json` 의 `prompt` 키)

## 코드와 프롬프트 분리

시스템/유저 프롬프트 문구는 전부 `prompts/*.md` 에 있고, 코드는 `{{변수}}` 채우기(`prompt_loader.py`)와
LLM 호출·파싱만 한다 — 실제로 모델에 무엇이 어떤 순서로 들어가는지 `.py` 를 안 읽고 `.md` 만 봐도
알 수 있다.

| 프롬프트 파일 | 역할 | 채워지는 변수 |
|------|------|------|
| `prompts/m4_common.md` | M4·M6 두 LLM 호출이 공유하는 페르소나(레퍼런스 리서치 디렉터) | (없음) |
| `prompts/m4_scout_system.md` | M4 지시문 — 문제 진단 + 장치·쿼리 제안 | (없음) |
| `prompts/m4_scout_user.md` | M4 입력 | `concept_line`, `ad_length`, `context_json` |
| `prompts/m4_synthesis_system.md` | M6 지시문 — 레퍼런스 반영 최종 문서 작성 | (없음) |
| `prompts/m4_synthesis_user.md` | M6 입력 | `concept_line`, `ad_length`, `context_json`, `creative_problem`, `devices_with_search_results_json` |

## 파일 구성

| 파일 | 역할 |
|------|------|
| `cli.py` | M0~M2 진입점(`--url`, v5_m0_m3.pipeline.run_m0_m2 재호출) |
| `cli_m3.py` | M3 placeholder 진입점(`--input <m0_m2.json>`, LLM 호출 없음) |
| `cli_m4.py` | M4 진입점(`--input <m0_m3.json>` `--concept` `--title` — 실행 폴더를 새로 만드는 단계) |
| `cli_m5.py` | M5 진입점(`--input <m4.json>` `--top_k` `--db_path`, LLM 호출 없음) |
| `cli_m6.py` | M6 진입점(`--input <m5.json>` `--llm_backend`) |
| `cli_m7.py` | M7 진입점(`--input <m6.json>` `--output`, LLM 호출 없음) |
| `pipeline.py` | `run_m0_m2`(재노출) / `run_m3_blank()` / `run_m4()`~`run_m7()` / `run_m4_m7()`(편의 래퍼) 오케스트레이션 |
| `context.py` | module0/m1/m2 → M4·M6 프롬프트용 압축 맥락(`build_context`) |
| `device_scout.py` | M4 — LLM 호출, 문제 진단 + 장치 후보·검색 쿼리 제안 |
| `retrieval.py` | M5 — 결정적 검색 실행, `evaluation.creative.reference_retrieval` 직접 호출(도구 호출 아님) |
| `synthesis.py` | M6 — LLM 호출, 검색 결과 반영 최종 문서 JSON |
| `render_markdown.py` | M7 — 구조화 출력 → DBH 문서 형식 Markdown 렌더링 |
| `prompt_loader.py` | `prompts/*.md` 로더 + `{{변수}}` 치환(md_parser.py 와 같은 방식, 이 패키지 전용) |
| `schemas.py` | `DeviceScoutOutput`/`M4SynthesisOutput` 등 pydantic 모델 |
| `prompts/` | 위 표 참고 |

## 사용법

```bash
# 1) M0~M2 (v5_m0_m3 와 동일 로직)
python -m generation.retrieval_pipeline.cli --url <제품 상세페이지 URL> \
    [--producttitle "제품명"] [--llm_backend cli|api] [--output_dir output/retrieval_pipeline] \
    [--guideline <가이드라인.md>]

# 2) M3 (공백 placeholder)
python -m generation.retrieval_pipeline.cli_m3 --input output/retrieval_pipeline/<slug>_m0_m2.json

# 3) M4 (한 줄 크리에이티브 원칙 입력 — 여기서 <날짜>_<제목>/ 실행 폴더가 새로 생긴다)
python -m generation.retrieval_pipeline.cli_m4 \
    --input output/retrieval_pipeline/<slug>_m0_m3.json \
    --concept "기기를 보여주지 말고, 집에서 세계와 연결되는 순간을 보여라." \
    --title "DBH_15초_CTV" \
    [--ad_length 15초] [--llm_backend cli|api]

# 4) M5 (장치별 벡터 DB 검색 실행 — M4를 다시 태우지 않고 재검색하고 싶으면 이 단계만 재실행)
python -m generation.retrieval_pipeline.cli_m5 \
    --input output/retrieval_pipeline/<날짜>_<제목>/m4.json \
    [--top_k 3] [--db_path output/vector_db]

# 5) M6 (검색 결과를 반영해 최종 문서 JSON 합성)
python -m generation.retrieval_pipeline.cli_m6 \
    --input output/retrieval_pipeline/<날짜>_<제목>/m5.json \
    [--llm_backend cli|api]

# 6) M7 (최종 Markdown 문서 렌더링)
python -m generation.retrieval_pipeline.cli_m7 \
    --input output/retrieval_pipeline/<날짜>_<제목>/m6.json
```

M5~M7 은 `--output_dir`/`--output` 을 생략하면 각각의 `--input` 파일과 같은 디렉터리에 이어서
저장한다 — `--title`/날짜 로직을 반복할 필요 없이 한 실행 폴더 안에 체인이 이어진다.

### 옵션

| 옵션 | 있는 CLI | 기본값 | 설명 |
|------|----------|--------|------|
| `--input` | `cli_m3`~`cli_m7` | (필수) | 바로 앞 단계가 저장한 JSON 경로 |
| `--concept` | `cli_m4` | (필수) | 한 줄 크리에이티브 원칙 |
| `--title` | `cli_m4` | (필수) | 실행 폴더명에 쓸 프로젝트 제목(슬러그화) |
| `--ad_length` | `cli_m4` | `15초` | 스토리라인 길이 |
| `--top_k` | `cli_m5` | `3` | 장치 1개당 검색해올 참조 광고 수(최대 20, `reference_retrieval._MAX_TOP_K`) |
| `--db_path` | `cli_m5` | `output/vector_db` | `evaluation/ad_concept_production` 이 적재한 ChromaDB 경로 |
| `--llm_backend` | `cli`, `cli_m4`, `cli_m6` | `cli` | `cli`(claude -p) \| `api`(Anthropic API, `env/api.env` `ANTHROPIC_API_KEY`) |
| `--output_dir` | `cli`, `cli_m3`, `cli_m4`, `cli_m5`, `cli_m6` | `cli`/`cli_m4`: `output/retrieval_pipeline`, 나머지: `--input` 과 같은 디렉터리 | 결과 저장 경로 |
| `--output` | `cli_m7` | `--input` 과 같은 디렉터리의 `creative_reference_ideas.md` | 최종 Markdown 저장 경로 |
| `--url` | `cli` | (필수) | 제품 상세페이지 URL |
| `--producttitle` | `cli` | `""` | 크롤 차단 시 web_search 복구에 쓸 제품 제목 힌트 |
| `--guideline` | `cli` | `None` | 브랜드 가이드라인 md 경로 — 지정 시 M1·M2 시스템 프롬프트에 최우선 지시로 삽입 |

`cli_m5.py`/`cli_m7.py` 는 LLM을 호출하지 않으므로 `--llm_backend` 가 없다.

## 출력 구조

`--title "DBH_15초_CTV"` 로 오늘(예: 2026-08-06) M4를 실행하면 그 아래 M5~M7 이 이어서 저장한다:

```
output/retrieval_pipeline/
├── <slug>_m0_m2.json                  M0~M2 산출물(cli.py)
├── <slug>_m0_m3.json                  M3 placeholder 포함 계약(cli_m3.py)
└── 20260806_DBH_15초_CTV/             cli_m4.py 가 새로 만드는 실행 폴더
    ├── m4.json                        M4 산출물 — prompt(실제 모델 입력) + creative_problem + device_candidates
    ├── m5.json                        M5 산출물 — search_queries(입력 쿼리) + search_results(원본 응답) + searches
    ├── m6.json                        M6 산출물 — prompt(실제 모델 입력, 검색결과 반영) + 최종 구조화 문서(devices/storylines/comparison/recommendation/common_checks/next_steps)
    └── creative_reference_ideas.md    M7 산출물 — 사람이 읽는 최종 문서(DBH 문서 형식)
```

`m4.json`/`m6.json` 각각의 `prompt` 키에 그 단계가 실제로 LLM에 보낸 system/user 원문이 그대로
남는다 — "실제 모델에 입력되는 데이터"를 확인하려면 이 두 파일만 보면 된다.

## 사전 준비

M5(검색)가 파이프라인에 항상 포함되므로, `output/vector_db` 에 두 컬렉션이 이미 적재돼 있어야 한다:

```bash
python -m evaluation.cli --mode strategy --video_id <ID> --data_dir <dir>
python -m evaluation.cli --mode ad_concept_production --video_id <ID> --data_dir <dir>
```

(`evaluation/ad_concept_production/README.md` 참고 — `ad_concept_reference`/`ad_production_reference`
두 컬렉션에 동시 적재된다.) 컬렉션이 비어 있으면 검색 결과가 항상 0건으로 나오고, M6은
"레퍼런스 미발견 — 원칙만 적용"으로 devices 를 채운다(하드 실패하지 않음).

그 외 사전 준비(`claude` CLI PATH, `env/api.env` 의 `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`)는
[`../v5_m0_m3/README.md`](../v5_m0_m3/README.md) 의 "사전 준비" 절과 동일하다(M0~M2 를 그대로
재사용하므로).

## 알려진 제약

- M3가 공백이므로, "M3 발산 컨셉 중 하나를 골라 M4에 넘기는" 워크플로우는 아직 없다 — 현재는
  사용자가 한 줄 원칙을 `--concept` 로 직접 입력한다.
- `retrieval.py`(M5) 는 장치 1개당 검색 1건만 실행한다(v5_m0_m3 M3 의 `_scout_emergent_lenses` 처럼
  "부족하면 재검색" 루프는 없음) — 검색 결과가 부실하면 `--top_k` 를 올려 M5만 재실행하거나
  `device_scout`(M4) 프롬프트(`prompts/m4_scout_system.md`)의 쿼리 설계 지시를 조정해 M4부터
  다시 실행한다.
- `segment_column`/`segment_value` 필터는 쓰지 않는다(자연어 `query_text` 검색만) — enum 값을
  틀리게 추측해 결과 0건이 되는 실패를 피하기 위한 의도적 단순화다(`evaluation/creative/reference_retrieval.py`
  자체도 "확신 없으면 query_text만 써라"라고 안내한다).
- `device_scout.py`(M4)/`synthesis.py`(M6) 는 `llm_adapter.chat_json()` 이 `{"error": ...}` 를
  반환하면 즉시 `RuntimeError` 를 던진다 — pydantic 의 기본 결측 필드 처리(빈 문자열/빈 배열)가
  LLM 호출 실패를 "장치 0개짜리 정상 결과"로 조용히 둔갑시키는 것을 막기 위해서다. 실행이
  실패하면 에러 메시지를 보고 해당 단계만 재실행하면 된다(앞 단계 파일은 그대로 남아 있다).
