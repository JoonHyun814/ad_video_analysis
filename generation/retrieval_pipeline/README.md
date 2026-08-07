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
- **M4(레퍼런스 기반 연출 아이디어)는 이 패키지에서 새로 설계한 단계**다. v5_m0_m3 의 M4(약한
  컨셉 킬)와 이름만 같을 뿐 역할이 다르다 — 컨셉을 평가·킬하는 게 아니라, 눈에 보이지 않는
  원칙을 "보이는 사건"으로 번역할 연출 장치를 레퍼런스와 함께 제안한다.
- LLM 호출 인프라(`chat_json` — claude -p CLI/Anthropic API 선택)는 `generation.v5_m0_m3.llm_adapter`
  를 그대로 재사용한다. 다만 이 파이프라인은 M3/M4~M9 처럼 **LLM이 tool_use 로 검색 여부를
  스스로 판단**하게 하지 않는다 — 아래 "왜 검색을 코드가 직접 실행하는가" 참고.

## M4 실행 흐름 — 왜 검색을 코드가 직접 실행하는가

v5_m0_m3 의 `--retrieval` 은 LLM에게 검색 도구(MCP/tool_use)를 쥐어주고 "쓸지 말지, 몇 건을
볼지"까지 LLM이 그때그때 판단하게 한다 — 그 결과 실제로 어떤 쿼리가 몇 번 나갔는지는 JSONL
로그(`<slug>_retrieval.jsonl`)를 봐야만 알 수 있고, "모델에 최종적으로 어떤 텍스트가 들어갔는지"는
별도로 재구성해야 한다. 이 파이프라인은 사용자 요청으로 **검색 실행 자체를 코드가 결정적으로
수행**하도록 뒤집었다 — 그래서 아래 세 가지가 항상 파일로 그대로 남는다:

1. **서칭에 입력되는 쿼리** — LLM이 제안한 검색어 그대로(`03_search_queries.json`)
2. **서칭 결과로 나온 데이터** — 벡터 DB가 실제로 반환한 원본(`04_search_results.json`)
3. **실제 모델에 입력되는 데이터** — 검색 결과를 반영해 다음 LLM 호출에 보낸 system/user
   프롬프트 원문 그대로(`01_scout_prompt.json`, `05_synthesis_prompt.json`)

M4는 LLM을 정확히 두 번 부른다:

```
1단계 device_scout   (LLM 호출 1회, 아직 검색 없음)
    한 줄 원칙 + M0~M2 맥락
    → 크리에이티브 문제 진단 + 연출 장치 후보 5~8개 + 장치별 검색 쿼리 제안

2단계 retrieval       (코드, 결정적 — LLM 아님)
    db.chromadb.creative_search.search_production_reference /
    search_concept_reference 를 장치마다 1회씩 그대로 호출(evaluation/ad_concept_production 이
    적재한 ad_production_reference / ad_concept_reference 컬렉션, 각각 data/ad_production_reference/·
    data/ad_concept_reference/)

3단계 synthesis       (LLM 호출 1회, 검색 결과 반영)
    한 줄 원칙 + M0~M2 맥락 + 크리에이티브 문제 + (장치, 실제 검색 결과)
    → 장치별 레퍼런스 인용 + 대안 스토리라인 3~4안 + 비교표 + 권고 + 공통 체크 + 다음 단계

4단계 render_markdown (코드)
    구조화 출력을 DBH_Creative_Reference_Ideas.md 형식 Markdown 문서로 렌더링
```

## 코드와 프롬프트 분리

시스템/유저 프롬프트 문구는 전부 `prompts/*.md` 에 있고, 코드는 `{{변수}}` 채우기(`prompt_loader.py`)와
LLM 호출·파싱만 한다 — 실제로 모델에 무엇이 어떤 순서로 들어가는지 `.py` 를 안 읽고 `.md` 만 봐도
알 수 있다.

| 프롬프트 파일 | 역할 | 채워지는 변수 |
|------|------|------|
| `prompts/m4_common.md` | 두 LLM 호출이 공유하는 페르소나(레퍼런스 리서치 디렉터) | (없음) |
| `prompts/m4_scout_system.md` | 1단계 지시문 — 문제 진단 + 장치·쿼리 제안 | (없음) |
| `prompts/m4_scout_user.md` | 1단계 입력 | `concept_line`, `ad_length`, `context_json` |
| `prompts/m4_synthesis_system.md` | 2단계 지시문 — 레퍼런스 반영 최종 문서 작성 | (없음) |
| `prompts/m4_synthesis_user.md` | 2단계 입력 | `concept_line`, `ad_length`, `context_json`, `creative_problem`, `devices_with_search_results_json` |

## 파일 구성

| 파일 | 역할 |
|------|------|
| `cli.py` | M0~M2 진입점(`--url`, v5_m0_m3.pipeline.run_m0_m2 재호출) |
| `cli_m3.py` | M3 placeholder 진입점(`--input <m0_m2.json>`, LLM 호출 없음) |
| `cli_m4.py` | M4 진입점(`--input <m0_m3.json>` `--concept` `--title` `--ad_length` `--top_k` `--llm_backend` `--db_path` `--output_dir`) |
| `pipeline.py` | `run_m0_m2`(재노출) / `run_m3_blank()` / `run_m4()` 오케스트레이션 |
| `context.py` | module0/m1/m2 → M4 프롬프트용 압축 맥락(`build_context`) |
| `device_scout.py` | 1단계 LLM 호출 — 문제 진단 + 장치 후보·검색 쿼리 제안 |
| `retrieval.py` | 2단계 결정적 검색 실행 — `db.chromadb.creative_search` 직접 호출(도구 호출 아님) |
| `synthesis.py` | 3단계 LLM 호출 — 검색 결과 반영 최종 문서 JSON |
| `render_markdown.py` | 구조화 출력 → DBH 문서 형식 Markdown 렌더링 |
| `prompt_loader.py` | `prompts/*.md` 로더 + `{{변수}}` 치환(md_parser.py 와 같은 방식, 이 패키지 전용) |
| `schemas.py` | `DeviceScoutOutput`/`M4SynthesisOutput` 등 pydantic 모델 |
| `prompts/` | 위 표 참고 |

## 사용법

```bash
# 1) M0~M2 (v5_m0_m3 와 동일 로직)
python -m generation.retrieval_pipeline.cli --url <제품 상세페이지 URL> \
    [--producttitle "제품명"] [--llm_backend cli|api] [--output_dir output/retrieval_pipeline]

# 2) M3 (공백 placeholder)
python -m generation.retrieval_pipeline.cli_m3 --input output/retrieval_pipeline/<slug>_m0_m2.json

# 3) M4 (한 줄 크리에이티브 원칙 입력)
python -m generation.retrieval_pipeline.cli_m4 \
    --input output/retrieval_pipeline/<slug>_m0_m3.json \
    --concept "기기를 보여주지 말고, 집에서 세계와 연결되는 순간을 보여라." \
    --title "DBH_15초_CTV" \
    [--ad_length 15초] [--llm_backend cli|api]

# M5(장치별 벡터 DB 검색, cli_m4 실행 시 이어서 자동 수행됨 — --top_k 만 바꿔 재검색하고
# 싶을 때만 따로 돌린다)
python -m generation.retrieval_pipeline.cli_m5 --input <run_dir>/m4.json [--top_k 3] [--db_path ...]
```

| 옵션(`cli_m4.py`) | 기본값 | 설명 |
|------|--------|------|
| `--input` | (필수) | `<slug>_m0_m3.json`(module0/m1/m2 포함, m3는 무시됨) |
| `--concept` | (필수) | 한 줄 크리에이티브 원칙 |
| `--title` | (필수) | 출력 폴더명에 쓸 프로젝트 제목(슬러그화) |
| `--ad_length` | `15초` | 스토리라인 길이 |
| `--llm_backend` | `cli` | `cli`(claude -p) \| `api`(Anthropic API, `env/api.env` `ANTHROPIC_API_KEY`) |
| `--output_dir` | `output/retrieval_pipeline` | 이 아래 `<날짜>_<제목>/` 폴더가 생긴다 |

| 옵션(`cli_m5.py`) | 기본값 | 설명 |
|------|--------|------|
| `--input` | (필수) | `m4.json` 경로(creative_problem/device_candidates 포함) |
| `--top_k` | `3` | 장치 1개당 검색해올 참조 광고 수(최대 20, `creative_search._MAX_TOP_K`) |
| `--db_path` | (미지정 시 자동) | ChromaDB 경로 — 안 주면 concept/production 컬렉션이 각자 `data/ad_concept_reference/`·`data/ad_production_reference/` 로 자동 결정된다 |
| `--output_dir` | `--input` 과 같은 디렉터리 | 결과(`m5.json`) 저장 경로 |

## 출력 구조

`--title "DBH_15초_CTV"` 로 오늘(예: 2026-08-05) 실행하면:

```
output/retrieval_pipeline/20260805_DBH_15초_CTV/
├── 01_scout_prompt.json        1단계 실제 모델 입력(system/user 원문)
├── 02_scout_output.json        1단계 출력(creative_problem + devices[].query_text 등)
├── 03_search_queries.json      서칭에 입력된 쿼리(장치별 query_text/collection/top_k)
├── 04_search_results.json      서칭 결과로 나온 데이터(벡터 DB 원본 응답)
├── 05_synthesis_prompt.json    2단계 실제 모델 입력(검색 결과가 반영된 system/user 원문)
├── 06_m4_output.json           최종 구조화 출력(devices/storylines/comparison/recommendation/...)
├── 07_creative_reference_ideas.md   사람이 읽는 최종 문서(DBH 문서 형식)
└── m0_m4.json                  {module0, m1, m2, m3, m4} — 다음 단계(M5+) 입력용
```

## 사전 준비

`--retrieval` 이 항상 켜져 있는 파이프라인이므로(M4는 검색 없이 실행할 수 없다),
`data/ad_concept_reference/`·`data/ad_production_reference/` 에 두 컬렉션이 이미 적재돼
있어야 한다:

```bash
python -m evaluation.cli --mode strategy --video_id <ID> --data_dir <dir>
python -m evaluation.cli --mode ad_concept_production --video_id <ID> --data_dir <dir>
```

(`evaluation/ad_concept_production/README.md` 참고 — `ad_concept_reference`/`ad_production_reference`
두 컬렉션에 동시 적재된다.) 컬렉션이 비어 있으면 검색 결과가 항상 0건으로 나오고, M4는
"레퍼런스 미발견 — 원칙만 적용"으로 devices 를 채운다(하드 실패하지 않음).

그 외 사전 준비(`claude` CLI PATH, `env/api.env` 의 `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`)는
[`../v5_m0_m3/README.md`](../v5_m0_m3/README.md) 의 "사전 준비" 절과 동일하다(M0~M2 를 그대로
재사용하므로).

## 알려진 제약

- M3가 공백이므로, "M3 발산 컨셉 중 하나를 골라 M4에 넘기는" 워크플로우는 아직 없다 — 현재는
  사용자가 한 줄 원칙을 `--concept` 로 직접 입력한다.
- `retrieval.py` 는 장치 1개당 검색 1건만 실행한다(v5_m0_m3 M3 의 `_scout_emergent_lenses` 처럼
  "부족하면 재검색" 루프는 없음) — 검색 결과가 부실하면 `--top_k` 를 올리거나 `device_scout`
  프롬프트(`prompts/m4_scout_system.md`)의 쿼리 설계 지시를 조정한다.
- `segment_column`/`segment_value` 필터는 쓰지 않는다(자연어 `query_text` 검색만) — enum 값을
  틀리게 추측해 결과 0건이 되는 실패를 피하기 위한 의도적 단순화다(`db/chromadb/creative_search.py`
  자체도 "확신 없으면 query_text만 써라"라고 안내한다).
