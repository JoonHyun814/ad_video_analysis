# generation/v5_m0_m3 모듈

`C:\WORKSPACE2\v5_pipeline\shortform-pipeline-master_test` (DR-CTV v5 파이프라인)의
**MODULE 0~9**(소재 인제스트 → 소비자 인사이트 → 경쟁 포지셔닝 → 컨셉 발산 → 비평·킬 →
스크립트 → 레드팀 → 검증 → 콘티)를 이 프로젝트로 복사·이식한 독립 파이프라인이다. 소스
프로젝트는 **import 하지 않으며 수정하지도 않는다** — 필요한 로직을 파일 단위로 복사한 뒤
이 프로젝트의 인프라(claude -p CLI, OpenAI Vision API, 로컬 JSON 파일 저장)에 맞게 최소한으로
재배선했다.

기존 `generation/`(G1~G6, 클리셰 인지 파이프라인)과는 **별개의 파이프라인**이다 — 서로 참조하지
않는다.

## 두 개의 독립 파이프라인

사용자 요청에 따라 **M0~M3 와 M4~M9 를 따로 실행**할 수 있게 나눴다. M4~M9 는 M0~M3 의 결과
JSON(`{"module0","m1","m2","m3"}`)을 입력으로 받는다 — 즉 M0~M3 를 한 번 실행해두면 그 결과로
M4~M9 를 몇 번이든(다른 `--style` 로) 다시 실행할 수 있다.

```
python -m generation.v5_m0_m3.cli        --url ...              →  <slug>_m0_m3.json
python -m generation.v5_m0_m3.cli_m4_m9  --input <slug>_m0_m3.json  →  <slug>_m4_m9.json
```

## M0~M9 란

| 단계 | 역할 | 산출 | 게이트 |
|------|------|------|--------|
| M0 | URL 크롤 → 제품 사실(facts)·USP·타깃·경쟁 후보 표준화 (코드, LLM 아님) | `productname`·`uspcandidates`·`facts`·`targethints`·`competitorcandidates` | — |
| M1 | JTBD 기반 소비자 인사이트 | `corejob`·`humantruth`·`target`·`forces` | — |
| M2 | Dunford 포지셔닝 + CEP×DBA 가용성 | `positioningstatement`·`uniqueattributes` | — |
| M3 | 앵커링 방지 컨셉 발산(빅아이디어 5~8개) | `concepts[]` | — |
| M4 | 독립 비평가가 약한 컨셉 킬 + 최종 1개 선정 | `verdict`·`killed[]`·`shortlist` | **GATE A**: shortlist 비면 reject(기록만, M5 는 계속 진행 — 아래 참고) |
| M5 | Schwartz 인지단계 + ABCD + Hook/Body/CTA 스크립트 | `script[]`·`hook`·`engine`·`cta` | — |
| M6 | 레드팀 프리모템(과거형 부검) | `failuremodes[]`·`killswitch` | **GATE B**: unresolvedcritical 있으면 block |
| M7 | 합성 오디언스 저비용 검증 | `personas`·`verdict` | **GATE C**: verdict 기록만(아래 참고) |
| M9 | 3막 구조 스토리보드 콘티(씬·마이크로샷·타임코드) | `scenes[]`·`shots[]`·`usagecutscene` | — |

**M8 은 원본 소스에도 결번**이다(`v5-module-roles.md`: "M8 은 결번") — 이식 누락이 아니다.
M10(비주얼 디렉터)·M11(통합 스토리보드)·M12(영상 생성)는 이번 이식 범위 밖이다.

## GATE 처리 방식 — 원본과 다른 점

원본에는 두 실행 경로가 있고 GATE A 처리가 서로 다르다:
- `orchestrator.py`(`start_run`, classic): GATE A reject 시 M3 를 최대 2회 자동 재발산하고,
  그래도 reject 면 **`if ga == "reject": return` 으로 멈춰서** `status=awaitingreview` 로 정지한다.
- `studio_orchestrator.py`(`run_full`, "풀런"): 반송 루프가 끝난 뒤 **ga 값을 검사하는 코드
  자체가 없다** — reject 여도 그냥 M5 로 진행해버린다(의도된 설계라기보단 가드 누락으로 보임).

이 파이프라인은 **사용자 요청에 따라 `run_full` 쪽(reject 여도 통과)을 재현**했다 — GATE A
reject 는 `gates.a = "reject"` 로 기록만 하고 M5 로 계속 진행한다(`pipeline.py` `run_m4_m9()`
안의 주석 참고). 이때 M5 는 원본과 동일하게 `((h.get(4,{}) or {}).get("selected") or [{}])[0]`
로 `selectedconcept` 를 뽑는데, `selected` 가 정말 비어 있으면 빈 dict `{}` 가 그대로 M5 입력이
되어 "선정된 컨셉 없이" 스크립트가 만들어질 수 있다(원본과 동일한 결과 — 버그를 고치지 않고
그대로 이식했다).

GATE B/C 는 이 요청 범위 밖이라 기존 방침 그대로다:

- **GATE B block** → 즉시 중단(M7/M9 진행 안 함), `unresolvedcritical` 을 확인해 필요한
  단계부터 수동으로 재시도해야 한다. 원본의 owner 모듈 자동 재실행 루프는 그 반송 대상(M1~M5
  중 일부)이 이미 끝난 별개 실행 결과일 수 있어 이식하지 않았다.
- **GATE C(M7)** → 이 프로젝트엔 원본의 "인간 검수 대기(awaitingreview)" UI가 없다. verdict 를
  기록만 하고 항상 M9 로 계속 진행한다(소스의 `run_full` 자동진행 모드와 동일한 정책).

## 소스 대비 변경 사항 (사용자 승인/설계 결정)

| 항목 | 원본 | 이 프로젝트 |
|------|------|------|
| LLM 텍스트 호출 | `app.services.llm_client.llm_chat` (Anthropic API 직접 호출 + tier 별 모델 자동 라우팅 + DB 로깅) | `llm_adapter.chat_json` — `--llm_backend cli`(기본, `utils.llm_caller.call_claude` = claude -p CLI) 또는 `--llm_backend api`(Anthropic API 직접, `env/api.env` `ANTHROPIC_API_KEY`) 중 선택 |
| 비전(이미지) 호출 | 동일 게이트웨이의 vision 메시지 | `llm_adapter.vision_json` → `utils.openai_caller.call_openai_with_images` (claude -p 는 이미지 미지원) |
| 카테고리(category3id) 분류 | 소스 프로젝트 MySQL `category` 테이블 | `category_lookup.py` — 같은 테이블을 **읽기 전용**으로 직접 조회(`env/v5_category_db.env`, 소스 RDS 접속정보 복사) |
| 실행 상태 저장 | `store.py`(MySQL `v5runs`/`v5moduleoutputs`) | 없음 — 파이프라인 결과를 JSON 파일로만 저장(`output/v5_m0_m3/`) |
| 소재 이미지 참조 생성 | `image_gen.ensure_product_references`(S3 업로드) | 제외 — M10~M12(비주얼·영상 생성) 전용이라 범위 밖 |
| persona_v2 보강 | `gpt_json.gpt_chat_json`(소스 DB `prompts` 테이블, 코드 폴백 없음) | 제외 — 사용자 승인 DB 범위가 카테고리 테이블(읽기 전용)뿐이라 이식 불가 |
| GATE A reject 시 정지 | `orchestrator.py`(classic) 는 정지, `studio_orchestrator.run_full()` 은 검사 없이 통과 | `run_full` 쪽(통과)을 재현 — 위 "GATE 처리 방식" 참고 |
| GATE A/B 자동 반송 루프(M3 재발산/owner 모듈 재실행) | `orchestrator.py`/`studio_orchestrator.py` 최대 2회 | 제외 — 반송 대상(M1~M3)이 별개 파이프라인 실행 결과라 이 함수 안에서 되돌릴 수 없음 |
| 게이트(M4/M6/M7) 상위 모델 opt-in | `_gate_model`(basicvalue 토글로 gpt-5.5 등 스위칭) | 제외 — claude -p 는 모델 스위칭 개념이 없음 |
| M5 설득엔진 반-수렴 | `_recent_engines`(소스 DB `v5moduleoutputs` 최근 run 조회) | 제외 — 이 프로젝트엔 run 이력 테이블이 없고 단발 CLI 라 "최근 run" 개념이 없음 |
| M9 영상 스타일 자동 선택 | `video_style.pick_style_llm`(DB 최근 스타일 반-수렴 + LLM 판정) | 제외 — `cli_m4_m9.py --style` 명시 인자만 지원(미지정 시 cinematic) |
| M10/M11 전용 로직(비주얼 디렉터·통합 스토리보드·캡션 규칙) | `modules.py`/`video_style.py` 나머지 | 제외 — M0~M9 실행 경로에서 호출되지 않음 |

## 파일 구성

| 파일 | 역할 |
|------|------|
| `cli.py` | M0~M3 진입점 (`--url` `--llm_backend` `--retrieval`, 켜면 `<slug>_retrieval.jsonl` 사용 기록도 저장) |
| `cli_m4_m9.py` | M4~M9 진입점 (`--input <m0_m3.json>` `--style` `--llm_backend`) |
| `pipeline.py` | `run_m0_m3()` / `run_m4_m9()` 오케스트레이션 |
| `module0_ingest.py` | MODULE 0 — 소재 인제스트(코드) |
| `v1_bridge.py` | URL 크롤(curl_cffi→curl→httpx) + 소재 분석 LLM 호출 |
| `material_extractor.py` | v1 분석 dict → `ProductInfoCard` |
| `product_classifier.py` | 제품 형태·관여도 룰 기반 분류 |
| `page_section_ocr.py` | 상세페이지 이미지 비전 OCR → USP 후보 |
| `usp_extractor.py` | 대표 USP 한 문장 도출 |
| `usp_score_rules.py` | USP 명확성/신뢰성 룰(page_section_ocr 랭킹용) |
| `brand_research_service.py` | 브랜드 지식 추론 + web_search 경쟁사/제품 복구 |
| `narrative_docs.py` | 서사 참고자료(`reference_doc/narrative/`) 로더 |
| `category_lookup.py` | 소스 RDS `category` 테이블 읽기 전용 조회 |
| `md_parser.py` | `prompts/common.md`·`module{1,2,3,4,5,6,7,9}.md` 로더 |
| `modules_runner.py` | MODULE 1~9 LLM 러너(핸드오프 조립·게이트 판정·M9 타임코드 보정·재시도) |
| `video_style.py` | M9 촬영 포맷 프리셋(cinematic/ugc/demo/asmr 등) |
| `llm_adapter.py` | LLM 텍스트 백엔드 스위치(claude -p CLI / Anthropic API) + OpenAI Vision 어댑터 + `--retrieval` 도구 연결(`evaluation/creative` 참조 광고 검색, MCP 또는 Anthropic tool_use) |
| `schemas.py` | `ProductInfoCard` 등 pydantic 모델 |
| `brand_research_prompts.py` | 브랜드 리서치 system/user 프롬프트 |
| `prompts/` | `common.md`·`module1~7,9.md` (원본 그대로, M8 없음) |
| `reference_doc/narrative/` | `00_core.md`·`01_narrative_structures.md` (원본 그대로) |

## 사용법

```bash
# 1) M0~M3
python -m generation.v5_m0_m3.cli --url <제품 상세페이지 URL> [--producttitle "제품명"] \
    [--llm_backend cli|api] [--retrieval] [--output_dir output/v5_m0_m3]

# 2) M4~M9 (1의 결과를 입력으로)
python -m generation.v5_m0_m3.cli_m4_m9 --input output/v5_m0_m3/<slug>_m0_m3.json \
    [--style cinematic] [--llm_backend cli|api]
```

- `--producttitle`: 크롤이 봇 차단되면 web_search 복구 단계의 1순위 검색 단서로 쓰인다.
- `--style`: `cinematic`(기본)·`ugc`·`demo`·`asmr`·`testimonial`·`vlog`·`comparison`·`reaction`·
  `lifestyle`·`howto` 중 하나. M9 콘티의 촬영/연출 포맷을 결정한다.
- `--llm_backend`: 텍스트 LLM 호출 방식(M0~M9 전 구간의 module0/M1~M9 호출에 적용, 비전 OCR
  제외 — 아래 "알려진 제약" 참고).
  - `cli`(기본): 로컬 Claude Code CLI(`claude -p`) 서브프로세스 호출. API 키 불필요, `claude`
    가 PATH 에 있어야 한다. 서브프로세스 기동 오버헤드가 있어 기본 timeout 을 이 프로젝트
    다른 CLI 헬퍼 기본값(300초)의 **2배(600초)** 로 늘렸다(`llm_adapter._CLI_TIMEOUT_MULTIPLIER`).
  - `api`: Anthropic Messages API 직접 호출(`env/api.env` 의 `ANTHROPIC_API_KEY` 필요, 모델은
    `llm_adapter._API_DEFAULT_MODEL` 고정 — 원본의 tier 별 자동 모델 라우팅은 이식하지 않았다).
    응답 상한은 `llm_adapter._API_MAX_TOKENS`(24000) — M3 는 컨셉 5~8개 × 필드 10개+(`referencedvideoid`/
    `referencedelement` 포함)라 검색 도구까지 쓰면 응답이 길어지고, 렌즈별 타겟 검색(아래
    `--retrieval` 항목 참고)으로 검색 결과가 여러 건 쌓이면 모델이 그걸 종합하는 thinking
    토큰만으로 12000 을 거의 다 써버려 정작 JSON 답변이 잘리는 사례가 실측됐다 — 그래서 24000
    으로 올렸다. `_API_MAX_TOKENS` 가 커서 Anthropic SDK 의 비-스트리밍 10분 제한 가드에
    걸리므로(`ValueError: Streaming is required...`), `llm_adapter._create_message()` 가
    `client.messages.create` 대신 스트리밍(`client.messages.stream(...).get_final_message()`)
    으로 호출하고 최종 Message 객체만 돌려준다 — 호출부(`_chat_json_api`/
    `_chat_json_api_with_tools`)는 이전과 동일하게 다룬다.
- `--retrieval`(cli.py 전용, M0~M3 만): M1~M3 시스템 프롬프트에 `evaluation/creative` 크리에이티브
  벡터 DB(기존 광고 81편·요소 1592건)를 검색하는 도구(`search_reference_ads`/`list_segment_columns`,
  `creative-retrieval` MCP 서버)를 붙인다. 어떤 세그먼트 컬럼/값으로 몇 건(top_k)을 검색할지는
  LLM 이 그때그때 판단한다(강제 호출 아님). 두 `--llm_backend` 모두 지원하지만 전송 방식이
  다르다 — `cli`: `claude -p --mcp-config .mcp.json`, `api`: Anthropic 네이티브 tool_use 루프
  (`llm_adapter._chat_json_api_with_tools`). 첫 호출은 임베딩 모델(bge-m3) 콜드스타트로 15~20초
  안팎 걸리지만 이후 호출은 초 단위로 빠르다(`reference_retrieval.py` 가 프로세스당
  `chromadb.PersistentClient` 를 캐싱 — 예전엔 검색 1건마다 재오픈해서 `claude -p` 경유 호출이
  30분 넘게 멈추는 버그가 있었고, 매칭 영상별로 N번 나눠 하던 크리에이티브 요소 조회도 단일
  `$in` 쿼리로 합쳤다). 자세한 도구 스펙은
  [`../../evaluation/creative/README.md`](../../evaluation/creative/README.md) 참고.
  M3 는 M1/M2 와 달리 "참고만 하고 베끼지 마라"에 그치지 않고 두 가지를 추가로 안내받는다
  (`modules_runner._run_module_core` 의 `n == 3` 분기):
  1. **포괄적 검색 1회 대신 렌즈별 타겟 검색**을 유도한다 — 선택한 전략 렌즈마다 필요한
     '증명 방식'이 다르므로(데모·증거 렌즈 → 실측 비교 데모 사례, 적 의인화 렌즈 → 경쟁/현상유지를
     캐릭터화한 사례 등) 유망한 렌즈 2~3개 이상을 골라 각각 좁은 쿼리로 따로 검색하게 하고,
     결과 과다를 막기 위해 검색 1건당 `top_k` 는 2~4로 작게 잡으라고 안내한다.
  2. 검색 도구를 호출했다면 발산한 컨셉 중 **가능한 한 여러 개**(1개에 그치지 않고)에는 그
     컨셉의 렌즈로 검색한 결과의 `notable_elements`(opening_hook/casting_direction/
     narrative_pattern/sensory_demo_shot) 중 구체적 연출 기법 하나를 변형해 반영하라고 안내한다.

  반영 여부는 M3 출력 `concepts[].referencedvideoid`/`referencedelement` 로 추적 가능하다 —
  실제로 반영했으면 참조한 `video_id`와 (원본 기법 → 변형) 1줄, 반영하지 않았으면 둘 다 빈
  값이다(지어내는 것 금지, 반영한 컨셉 수보다 정확성이 우선). 검증 결과: 강제 재검색 테스트에서
  포괄적 검색 1회로는 7개 컨셉 중 1개만 인용을 남겼지만, 렌즈별 타겟 검색으로 바꾸자 5개로
  늘었다 — 인용된 `video_id`들의 실제 DB 내용을 대조해보면 전부 정확했다(할루시네이션 아님).
- 결과: `<output_dir>/<slug>_m0_m3.json`(`{"module0","m1","m2","m3"}`), `<slug>_m4_m9.json`
  (`{"m3"(검증마커 반영)","m4"~"m9","gates":{"a","b","c"}}`).
- `--retrieval` 사용 시 `<output_dir>/<slug>_retrieval.jsonl` 에 검색 도구 사용 기록이 남는다
  (도구가 한 번도 호출되지 않았으면 파일 자체가 생기지 않는다 — "검색 안 씀"의 정상적인 표시).
  한 줄 = 호출 1건: `{"timestamp","stage"(예: "M1"·"M2"·"M3"·"M0:material_analysis"),"tool",`
  `"arguments","result_count","video_ids","segment_filter","error"}`. `--llm_backend cli`/`api`
  모두 같은 형식으로 기록된다(둘 다 `evaluation.creative.reference_retrieval._log_call` 을 거침 —
  cli 는 MCP 서브프로세스가, api 는 같은 프로세스가 직접 씀).
- M0 가 제품을 특정하지 못하거나, GATE A reject/GATE B block 이거나, 어느 모듈이 재시도 후에도
  빈 응답이면 `error` 키가 채워지고 그 이후 단계는 실행되지 않는다.

## 사전 준비

1. `env/api.env` 에 `OPENAI_API_KEY` 입력 — 비전 OCR(`page_section_ocr`)과 브랜드 리서치
   (`brand_research_service`, web_search 포함)에 필요하다. 비어 있으면 두 기능 모두
   graceful 하게 빈 결과로 skip 된다(파이프라인은 계속 진행). `--llm_backend` 선택과 무관하게
   항상 필요하다(위 "알려진 제약" 참고).
2. `--llm_backend cli`(기본) 사용 시: `claude` CLI 가 PATH 에 있어야 한다
   (`utils.llm_caller.call_claude` 가 `claude -p` 로 호출).
   `--llm_backend api` 사용 시: `env/api.env` 에 `ANTHROPIC_API_KEY` 입력(이미 포함됨).
3. `env/v5_category_db.env` — 소스 RDS `category` 테이블 접속 정보(이미 포함됨, **읽기 전용
   SELECT만** 실행한다). 이 프로젝트 자체 DB(`env/db.env`, `ad_video_label`)와는 무관하다.
4. `--retrieval` 사용 시: `output/vector_db` 에 `evaluation.creative` 벡터 DB가 이미 적재되어
   있어야 한다(`python -m evaluation.cli --mode creative --load_vector ...`). 저장소 루트의
   `.mcp.json` 이 `creative-retrieval` MCP 서버를 등록한다(커밋됨, 공유).
   **`--llm_backend cli` 와 함께 쓸 때만** 추가로 승인이 필요하다 — 이 저장소는 `.gitignore` 로
   `.claude/`(개인 로컬 상태)를 전부 제외하므로, `claude -p` 헤드리스 호출이 "Pending approval"
   에 막히지 않으려면 각자 로컬에 `.claude/settings.json` 을 만들어 아래 내용을 넣거나
   (`{"enabledMcpjsonServers": ["creative-retrieval"]}`), 그 프로젝트 디렉터리에서 `claude` 를
   한 번 대화형으로 실행해 서버를 승인해야 한다(1회만). **`--llm_backend api` 는 이 승인 절차가
   전혀 필요 없다** — Claude Code 의 MCP 신뢰 체계를 타지 않는 Anthropic 네이티브 tool_use 라서
   설치 직후 바로 동작한다. 승인 절차를 신경 쓰고 싶지 않으면 `--retrieval` 은 `--llm_backend api`
   조합을 권장한다.
5. 신규 패키지: `beautifulsoup4`, `curl_cffi`, `anthropic`, `mcp[cli]` (`setup_venv.ps1`/`Dockerfile` 에 추가됨).

## 알려진 제약

- `page_section_ocr`/`material_extractor` 의 비전 분석은 `--llm_backend` 선택과 무관하게 항상
  OpenAI Vision(`gpt-4o-mini` 기본)을 쓴다 — claude -p 도 이 어댑터의 Anthropic API 경로도
  이미지 첨부를 지원하지 않는다.
- `--llm_backend api` 는 원본의 tier 별 자동 모델 라우팅(간단 작업은 sonnet, 복잡 작업은 opus)
  이 아니라 고정 모델 하나(`llm_adapter._API_DEFAULT_MODEL`)만 쓴다. 실패해도 cli 백엔드로
  자동 폴백하지 않는다(선택한 백엔드로만 시도).
- `personas`(persona_v2 보강)는 항상 빈 배열이다 — 소스의 해당 기능이 이 프로젝트에 없는 DB
  프롬프트 테이블에 의존해 이식하지 않았다. `targethints` 는 `targetaudience`/`heropersonabrief`
  로만 채워진다.
- got-scraping(Node.js 스크립트)·MCP 브라우저 크롤러는 소스 프로젝트 로컬 환경 전용이라
  제외했다 — `curl_cffi → curl(모바일 UA) → httpx` 체인만으로 크롤을 시도한다.
- GATE A/B 는 자동 반송되지 않는다("GATE 처리 방식" 절 참고) — 재시도는 사용자가 수동으로.
- M9 는 원본처럼 씬 타임코드·마이크로샷 보정, 엔딩 팩샷 예약(13~15초), 사용 완결 컷/컷 대비
  계약 위반 시 1회 재생성을 코드로 수행한다(하드 실패 없음 — 재시도 후에도 위반이면 경고만
  남기고 통과).
- `--retrieval` 은 M4~M9(`cli_m4_m9.py`)에는 없다 — 사용자 요청 범위가 M0~M3 라 그쪽에만
  연결했다. 도구를 쓸지·안 쓸지, 몇 건을 볼지는 매 LLM 호출마다 모델이 새로 판단한다(이전
  호출에서 검색한 결과를 "기억"해 재사용하지 않음 — M1/M2/M3 가 각자 필요하면 각자 검색한다).
