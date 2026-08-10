# generation/retrieval_pipeline 모듈

한 줄 크리에이티브 원칙(예: "기기를 보여주지 말고, 집에서 세계와 연결되는 순간을 보여라.")을
입력받아, **자사 광고 벡터 DB에서 실제로 검색한 참조 광고**를 근거로 연출 장치(device)를
제안하는 파이프라인이다.

> **개편 중(진행형)**: 기존 M3~M7(장치 후보 제안 → 코드가 검색 실행 → 결과 반영 합성 →
> Markdown 렌더링) 설계를 걷어내고 처음부터 다시 설계하고 있다. 지금은 M3(장치 8개 생성)까지만
> 있다 — 스토리라인·비교/권고·Markdown 렌더링 같은 뒷단계는 아직 없다(사용자 요청 —
> "다 지우고 한단계씩 개발").

## v5_m0_m3 와의 관계

- **M0~M2(소재 인제스트→인사이트→포지셔닝)는 `generation/v5_m0_m3` 와 완전히 동일한 로직을
  그대로 재사용한다** — `cli.py` 는 `generation.v5_m0_m3.pipeline.run_m0_m2()` 를 그대로
  호출할 뿐, M0~M2 를 이 패키지 안에 다시 구현하지 않는다.
- **M3(장치 8개 생성)는 이 패키지에서 새로 설계한 단계**다. LLM 호출 인프라는 v5_m0_m3 와
  달리 이 패키지 전용 `tool_chat.py` 를 쓴다(아래 "왜 v5_m0_m3.llm_adapter 를 그대로 안
  쓰는가" 참고) — M0~M2(`cli.py`)만 v5_m0_m3 의 `run_m0_m2()`/LLM 어댑터를 재사용한다.

## M3 실행 흐름 — LLM이 스스로 검색하며 장치를 완성한다

이전 설계(device_scout(LLM, 검색 없음) → retrieval(코드, 결정적 검색) → synthesis(LLM, 검색
결과 반영))는 "검색은 코드가 결정적으로 실행"하는 방식이었다. 이번 개편은 반대로 **LLM에게
`search_chromadb` 검색 도구를 직접 쥐어주고, 장치 후보를 검증하기 위해 몇 번이든 스스로 검색
판단을 내리게** 한다 — 분석(문제 진단)·검색(도구 호출)·완성(장치 8개)이 LLM 호출 1회 안에서
전부 일어난다.

```
M3 device_generation   (LLM 호출 1회 — 그 안에서 도구 왕복은 여러 번)
    m0~m2 맥락(+선택적 한 줄 원칙)
    → 크리에이티브 문제 진단
    → search_chromadb(collection="category_analysis"|"scenario_analysis", query_text=...) 를
      장치 후보마다 필요한 만큼 자율 호출해 근거 수집
    → 정확히 장치 8개(근거 인용 포함) 완성
```

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
| `prompts/m3_common.md` | 페르소나(레퍼런스 리서치 디렉터) | (없음) |
| `prompts/m3_system.md` | 지시문 — 문제 진단 + 도구로 근거 수집 + 장치 8개 완성 | (없음) |
| `prompts/m3_user.md` | 입력 | `concept_line`, `ad_length`, `context_json` |

## 파일 구성

| 파일 | 역할 |
|------|------|
| `cli.py` | M0~M2 진입점(`--url`, v5_m0_m3.pipeline.run_m0_m2 재호출) |
| `cli_m3.py` | M3 진입점(`--input <m0_m2.json>` `--title` `--concept`(선택) `--ad_length` `--llm_backend` `--output_dir`) |
| `pipeline.py` | `run_m0_m2`(재노출) / `run_m3()` 오케스트레이션 |
| `context.py` | module0/m1/m2 → M3 프롬프트용 압축 맥락(`build_context`) |
| `device_generation.py` | M3 — 프롬프트 조립 + `tool_chat.run()` 호출 + `DeviceGenerationOutput` 파싱 |
| `tool_chat.py` | LLM이 `search_chromadb` 를 tool_use 로 자율 호출하는 왕복 루프(cli: MCP, api: Anthropic 네이티브 tool_use) |
| `prompt_loader.py` | `prompts/*.md` 로더 + `{{변수}}` 치환(이 패키지 전용) |
| `schemas.py` | `DeviceGenerationOutput`/`Device`/`ReferenceAdCitation` pydantic 모델 |
| `prompts/` | 위 표 참고 |

## 사용법

```bash
# 1) M0~M2 (v5_m0_m3 와 동일 로직)
python -m generation.retrieval_pipeline.cli --url <제품 상세페이지 URL> \
    [--producttitle "제품명"] [--llm_backend cli|api] [--output_dir output/retrieval_pipeline]

# 2) M3 (분석 + 도구 호출로 연출 장치 8개 완성)
python -m generation.retrieval_pipeline.cli_m3 \
    --input output/retrieval_pipeline/<slug>_m0_m2.json \
    --title "DBH_15초_CTV" \
    [--concept "기기를 보여주지 말고, 집에서 세계와 연결되는 순간을 보여라."] \
    [--ad_length 15초] [--llm_backend cli|api]
```

| 옵션(`cli_m3.py`) | 기본값 | 설명 |
|------|--------|------|
| `--input` | (필수) | `<slug>_m0_m2.json`(module0/m1/m2 포함) |
| `--concept` | (없음, 선택) | 한 줄 크리에이티브 원칙 — 안 주면 m0~m2 맥락(포지셔닝 성명서·가치 제안)에서 LLM이 직접 도출 |
| `--title` | (필수) | 출력 폴더명에 쓸 프로젝트 제목(슬러그화) |
| `--ad_length` | `15초` | 스토리라인 길이 |
| `--llm_backend` | `cli` | `cli`(claude -p + chromadb-explorer MCP) \| `api`(Anthropic API 직접 tool_use, `env/api.env` `ANTHROPIC_API_KEY`) |
| `--output_dir` | `output/retrieval_pipeline` | 이 아래 `<날짜>_<제목>/` 폴더가 생긴다 |

## 출력 구조

`--title "DBH_15초_CTV"` 로 오늘(예: 2026-08-07) 실행하면:

```
output/retrieval_pipeline/20260807_DBH_15초_CTV/
├── m3.json                  {module0, m1, m2, concept_line, ad_length, context, prompt, creative_problem, devices[]}
└── DBH_15초_CTV.jsonl       search_chromadb 호출 로그(쿼리·컬렉션·검색 결과 원본, 호출마다 한 줄)
```

로그 파일명은 `--title` 슬러그(`log_prefix`)를 그대로 쓴다(사용자 요청). `db.chromadb.
tool_definitions.search_chromadb()`(기본 위치 `logs/search_chromadb/`)에 `SEARCH_CHROMADB_LOG_DIR`
환경변수로 이 실행의 출력 폴더를 지정해, 검색 로그가 산출물(`m3.json`)과 같은 날짜 폴더 안에
남게 한다(`tool_chat.py`) — 자세한 메커니즘은 [`../../db/README.md`](../../db/README.md)의
"호출 로깅" 절 참고.

`devices[]` 원소 하나(`Device`, `schemas.py`):

```json
{
  "name": "...", "mechanism": "...", "why_it_works": "...",
  "reference_ads": [{"video_id": 123, "collection": "category_analysis"}],
  "reference_thinking": "참조광고를 보니 ~하므로 ~의 ~를 가지고와서 ~하게 적용한다",
  "application_draft": "...", "impact": 4, "production_difficulty": "mid", "concept_fit": 5
}
```

## 사전 준비

M3는 검색 없이 실행할 수 없으므로, `data/category_analysis/`·`data/scenario_analysis/` 에 두
컬렉션이 이미 적재돼 있어야 한다:

```bash
python -m db.chromadb.importers.category [--data_root output/total]
python -m db.chromadb.importers.scenario [--data_root output/total]
```

(`../../db/README.md` 참고.) 컬렉션이 비어 있으면 검색 결과가 항상 0건으로 나오고, LLM은
"레퍼런스 미발견 — 원칙만 적용"으로 devices 를 채운다(하드 실패하지 않음).

`--llm_backend cli` 를 쓰려면 저장소 루트 `.mcp.json`의 `chromadb-explorer` MCP 서버를 최초
1회 승인해야 한다(`db/README.md` "Claude CLI(MCP)" 절 참고). `--llm_backend api` 를 쓰려면
`env/api.env` 의 `ANTHROPIC_API_KEY` 가 필요하다.

그 외 사전 준비(`claude` CLI PATH, `env/api.env` 의 `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`)는
[`../v5_m0_m3/README.md`](../v5_m0_m3/README.md) 의 "사전 준비" 절과 동일하다(M0~M2 를 그대로
재사용하므로).

## 알려진 제약

- 스토리라인·비교/권고·Markdown 렌더링 뒷단계는 아직 없다 — M3(장치 8개)까지만 구현됐고,
  다음 단계는 별도 요청으로 이어 붙인다("한단계씩 개발").
- `devices` 개수는 프롬프트로 "정확히 8개"를 지시할 뿐 스키마 레벨에서 강제하지 않는다 —
  LLM이 8개를 못 채우면 그보다 적게 나올 수 있다(하드 실패 대신 있는 그대로 반환).
- `search_chromadb` 호출 로그는 `<run_dir>/<title 슬러그>.jsonl` 에 남는다(파일명은
  `log_prefix`, 폴더는 `SEARCH_CHROMADB_LOG_DIR` 로 각각 강제 — `db/chromadb/
  tool_definitions.py` 의 항상-켜짐 로깅). `log_prefix`(파일명)는 `api` 백엔드에서
  `tool_chat.py`가 도구 호출을 가로채 강제 적용하지만, `cli`(MCP) 백엔드는 `claude -p`
  서브프로세스 내부에서 도구 왕복이 끝나 가로챌 수 없어 system 프롬프트 지시
  (`m3_system.md`)에만 의존한다 — 모델이 지시를 어기면 파일명이 샐 수 있다. `log_dir`
  (폴더)는 두 백엔드 모두 환경변수로 전달되므로 이 문제가 없다 — `claude -p` 서브프로세스와
  그 안에서 뜨는 MCP 서버(`db/chromadb/mcp_server.py`)가 부모 프로세스의 환경변수를 그대로
  물려받는다는 전제에 의존한다(둘 다 별도 `env=` 오버라이드 없이 스폰됨).
