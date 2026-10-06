# pikk 컷 태그 → 시나리오 에이전트 RAG 통합 계획서

작성일 2026-09-21 · 상태: **초안(팀 검토 전)** · 대상 저장소: `ad_video_analysis/`(RAG 서버·그래프·태깅), `aitive-Video-generation-agent/`(시나리오 에이전트)

## 1. 목적

`pikk_tagging`이 만드는 **컷 단위 기법 태그**를 시나리오 생성 에이전트(`scenario_agent_claude_litellm`,
`scenario_agent_claude`)가 쓰는 RAG에 연결해, "이 제품·이 서사 역할(HOOK, DEMO …)의 컷에는 어떤 연출을
쓰면 좋은가"를 **필터·통계·예시**로 검색할 수 있게 한다. 검증 없이 대량 적용하지 않고, 골든셋 → 파일럿 →
A/B → 전체 확장 순으로 진행하며 각 단계에 통과 기준(게이트)을 둔다.

## 2. 현황 — 코드에서 확인한 사실

### 2.1 RAG 서버 (`server/mcp_server.py`, `db/chromadb/tool_definitions.py`)
- 내부망 Streamable HTTP MCP(`chromadb-explorer-network`, 포트 8765, stateless). 노출 도구는 5개: `search_chromadb`, `search_chromadb_hybrid`, `fetch_by_video_id`, `search_visual`, `search_graph_pattern`.
- 도구 정의는 `tool_definitions.py`가 단일 소스이고, MCP 서버 2종(`server/mcp_server.py` 네트워크, `db/chromadb/mcp_server.py` stdio)과 Anthropic tool_use 경로가 공유한다. 에이전트 쪽 `scenario_agent_claude_litellm/tools.py`는 **도구 명세를 자체 복사본으로 따로 갖고 있다**(`TOOL_SPECS`, 역할 enum 중복 정의).
- 검색은 `collection`+`query_text`+`n_results`만 받는다. **메타데이터 필터 인자가 없다** (`search_query.py`는 `where` 없이 `col.query`).
- 하이브리드(`hybrid_search.py`): dense(bge-m3) + BM25(문자 bigram) → RRF(k=60), 후보는 `max(n×4, 20)`. **재정렬(reranker) 없음.** BM25 인덱스는 컬렉션 전체를 메모리에 올린다.
- 모든 호출이 `logs/search_chromadb/<날짜>/<log_prefix>.jsonl`에 쿼리·결과까지 기록된다(서버 쪽 파일).

### 2.2 세그먼트 필터는 코드에 있으나 도구로 노출되지 않았다
`db/chromadb/creative_search.py`의 `search_production_reference`/`search_concept_reference`는 `segment_column/segment_value` 필터(산업, 제품 카테고리, 길이 구간, 성별, USP 등)와 값 검증(`_validate_segment`), 허용 값 목록 도구(`list_*_segment_columns`)를 이미 갖고 있다. 이 모듈은 `generation/v5_m0_m3` 경로에서만 쓰이고 **시나리오 에이전트가 붙는 MCP 서버에는 올라가 있지 않다.** → 필터 도구를 새로 설계하기보다 이 패턴을 재사용한다.

### 2.3 그래프 (`db/graph/`, Kùzu)
- 스키마: `Campaign(video_id, brand_name, industry_category, product_category, campaign_objective, duration)`, `Sequence(id, video_id, position, role, cut_index)`, `Element(id, video_id, element_type, element_subtype, description, cut_refs)`, `Persona(category)`. 엣지 `HAS_TARGET_PERSONA`, `HAS_SEQUENCE`, `INCLUDES_ELEMENT`, `TRANSITIONS_TO`.
- 적재(`campaign_graph.py`)는 ChromaDB 3개 컬렉션에서 읽는다. **서사 역할과 컷의 대응은 위치 추정이다**: `category_analysis.role_sequence`(LLM이 나열한 역할 문자열)의 i번째 역할 ↔ 그 영상 요소들의 `cut_refs` 합집합 중 i번째로 작은 컷. 코드 주석과 서버 문서 모두 "best-effort 가정, 어긋날 수 있음"이라고 명시한다.
- `role_element_frequency`는 role(+persona)만으로 집계한다. `persona_category`는 데이터가 비어 항상 빈 결과.
- **정정**: 앞선 대화에서 "카테고리 조건부 통계가 안 된다"고 했는데, `Campaign`에 `industry_category`/`product_category`가 이미 있다. 막힌 것은 데이터가 아니라 **질의에 산업·카테고리 파라미터가 없는 것**이다.

### 2.4 기존 크리에이티브 요소 어휘 (`evaluation/creative/element_schema.py`)
`element_type` 13종(`opening_hook`, `casting_direction`, `narrative_pattern`, `persuasion_engine`, `narrative_form`, `tone_register`, `sensory_demo_shot`, `trust_device`, `product_shot`, `color_light_code`, `copy_device`, `sound_pattern`, `cta_device`)과 산업별 subtype 사전. 카메라 앵글·샷 크기·타이포그래피 같은 **촬영·연출 기법 축은 없다.** `color_light_code`(색·조명 설계)는 pikk의 `lighting_tone` 축과 일부 겹칠 수 있다.
`ad_production_reference`는 `cliche_aggregate`(세그먼트 내 빈도로 클리셰 판정)가 element_type 전체를 집계하므로, 여기에 새 element_type을 섞으면 기존 리포트가 바뀐다.

### 2.5 컷 단위 조인 키는 이미 있다
`ad_visual_reference`(CLIP)는 컷당 키프레임 1장, id `"{video_id}:cut_{cut:03d}"`, 메타데이터 `video_id/cut_index/image_path`. `pikk_tagging`도 같은 전처리(`total/<id>/cuts.json`, 최대 10컷)를 재사용하므로 **(video_id, cut_index)로 그대로 조인된다.** `datas/total`은 폴더 503개로 RAG의 502개 캠페인과 같은 코퍼스로 보인다(폴더명과 video_id 일치는 확인 필요).

### 2.6 시나리오 에이전트
입력은 제품명·상세페이지 URL·목표 길이. 도구 호출 루프(최대 25회, 예산 상한 $4 추정치)로 리서치한 뒤 `Scenario`(pydantic, `extra="forbid"`)를 구조화 출력한다. `Scene.narrative_role`은 RAG 서버의 `role` enum과 동일 어휘를 공유하고, 연출 관련 출력은 `camera_notes`/`visual_effects`/`sound_music_sfx` 자유 서술이다. 모든 호출은 `trace.json/html`에 기록된다. 프롬프트에 "적응적 검색(Self-RAG)" 원칙이 이미 있다.

### 2.7 pikk_tagging 현재 상태 (5개 영상, 컷 46개 실험 결과)
- 어휘 13종(camera 4, lighting_tone 6, graphics 3). 컷당 축별 2회 생성 → 다수결 → 태그별 재검증.
- 사이트 비율 대비 **타이포그래피 5.7배, 모션그래픽 3.8배, 하이키 1.9배 과다 태깅.** 실루엣·로우키·탑뷰는 0.2~0.3배. 골든셋 없이는 정확도를 알 수 없다.
- camera 축 JSON 파싱 실패가 46컷 중 3컷(1컷은 2회 모두 실패).
- 처리 속도: 영상 1개 약 4분(순차). 502개 순차 실행 시 약 33시간.

## 3. 설계 결정

| # | 결정 | 근거 |
|---|---|---|
| D1 | 컷 태그는 **새 컬렉션 `ad_cut_reference`** 에 적재한다. `ad_production_reference`에 섞지 않는다. | `cliche_aggregate`가 element_type 전체를 집계하고 `element_schema`가 enum을 강제한다. 기존 파이프라인(`generation/v5_m0_m3`) 회귀 위험 회피. |
| D2 | 컷 문서 = 기존 `cut_analysis`/`scene_analysis`의 컷 묘사 + 태그 텍스트. 임베딩 문서를 위한 **새 LLM 호출은 하지 않는다**(1차). | 이미 `datas/total/<id>/`에 있는 산출물 재사용. 비용·시간 절감. |
| D3 | 태그·역할은 메타데이터의 **태그별 bool 필드**(`tag_탑뷰=true` …)와 `narrative_role` 문자열로 저장한다. | ChromaDB 메타데이터는 스칼라(str/int/float/bool)만 허용하는 것으로 알고 있음 → 리스트 값 불가. **사용 중인 chromadb 버전에서 확인 필요.** |
| D4 | **서사 역할을 컷마다 직접 태깅**한다(축 `narrative_role`, 값은 `NarrativeRole` 10종). 기존 `role_sequence` 위치 추정은 유지하되 일치율을 지표로 잰다. | 2.3의 best-effort 약점 제거. 스키마·서버가 이미 같은 어휘를 공유. |
| D4-a | 역할 태깅은 **컷 위치(index/전체, 시각 비율)와 그 컷의 STT·OCR 텍스트**를 문맥으로 준다. 기법 태그와 달리 역할은 본질적으로 맥락 의존적이라 이 입력은 정당하다. 근거·재검증 규칙은 동일하게 적용. | HOOK/CTA는 컷 하나만 봐서는 판정 불가. |
| D5 | 그래프는 **`Cut`·`Technique` 노드를 추가**한다(`Campaign─HAS_CUT→Cut`, `Cut─USES_TECHNIQUE→Technique`, `Cut─NEXT_CUT→Cut`, `Cut.role` 직접 보유). 기존 `Sequence`/`Element`는 손대지 않는다. | 기존 도구·스키마 호환 유지. D1과 같은 이유. |
| D6 | 도구는 **기존 5개를 수정하지 않고 추가**한다: `search_cuts`, `search_technique_pattern`, `list_cut_vocab`. 에이전트는 플래그로 켜고 끈다(A/B 가능). | 후방 호환, 롤백 용이. |
| D7 | `search_technique_pattern`은 role × (산업/제품 카테고리) 조건에서 **빈도와 lift**(`P(기법│role,세그먼트) / P(기법│세그먼트)`)를 반환한다. persona는 쓰지 않는다. | 2.3 정정 사항. 단순 빈도는 하이키처럼 흔한 태그를 부풀린다. |
| D8 | 필터 값은 도구 명세의 **enum + `list_cut_vocab`** 으로 강제하고, 잘못된 값은 `_validate_segment` 방식으로 오류를 돌려준다. 어휘 원본은 `pikk_tagging/vocab.json` 하나로 하고 에이전트 쪽은 이를 복사하지 않고 서버에서 받아 쓴다. | 에이전트 `tools.py`의 역할 enum 이중 정의 문제 재발 방지. |
| D9 | 검색에 `where` 지원을 추가한다(dense는 `col.query(where=…)`, BM25는 메타데이터로 후보 필터). 재정렬은 **옵션 플래그**로 넣고 A/B에서 이득이 확인될 때만 켠다(후보: `BAAI/bge-reranker-v2-m3`). | 조사 결과에서 재정렬이 Agentic 반복보다 효과가 컸음. 서버 메모리·지연 증가 때문에 검증 후 결정. |
| D10 | 신뢰도 정책: **필터에는 재검증 통과(verified) + high 태그만**, medium은 가산점·표시용. | 필터는 오탐 하나가 후보 전체를 왜곡. |

## 4. 단계별 계획

### Step 1 — 태그 품질 확정 (골든셋 · 정의 보강 · 서사 역할 축)

| 작업 | 내용 | 산출물 |
|---|---|---|
| 1-1 골든셋 | 리뷰 GUI(`review.py`)로 검수. 1차 = 이미 만든 5개 영상(46컷, ★추천 29컷 우선). 2차 = **산업 카테고리별로 층화한 20개 영상, 200컷 이상**(Campaign.industry_category 분포 기준, 희소 기법이 실제로 나올 만한 영상 포함). 검수자 2인이 겹치는 30컷으로 **검수자 간 일치도** 측정. | `golden.json`, 일치도 리포트 |
| 1-2 정의·프롬프트 보강 | 타이포그래피/모션그래픽 제외 조건 강화(간판·자막·로고·UI 텍스트), 근거 문장 한국어 지시, 낮은 태깅률 기법(실루엣·로우키·탑뷰) 정의 재검토. camera 축 파싱 실패 시 1회 재시도. | `vocab.json`(버전 갱신), `prompts.py` |
| 1-3 서사 역할 축 | `narrative_role` 축 추가(단일값 + 근거). 입력 문맥 = 컷 위치, 시각 비율, 해당 컷 STT·OCR(D4-a). `role_sequence` 위치 추정과의 일치율 측정. | `vocab.json`, `prompts.py`, `schema.py`, 일치율 리포트 |
| 1-4 회귀 | 정의를 바꿀 때마다 `evaluate.py`로 골든셋 회귀, `stats.py`로 태깅률 확인. | 평가 로그 |
| 1-5 배치 러너 | 병렬 실행·이어하기(이미 `tags.json` 있으면 건너뜀)·429 백오프·진행/비용 요약. 현재 CLI는 영상별 순차. | `pikk_tagging/batch.py`(가칭) + README |

**게이트 G1 (제안 기준, 팀 합의 필요)**: 골든셋 기준 필터에 쓸 태그(D10)의 **precision ≥ 0.80**, micro-F1 ≥ 0.70, 사이트 비율 대비 태깅률 3배 초과 태그 없음, 역할 태깅의 검수자 일치도가 사람끼리의 일치도에 근접. 미달 태그는 어휘에서 제외하거나 가산점 전용으로 강등.

### Step 2 — 파일럿(50~100영상) + 검색 도구·그래프 프로토타입

| 작업 | 내용 | 변경 대상 |
|---|---|---|
| 2-1 대상 선정 | 산업 카테고리별 층화 60영상 내외(골든셋 20영상 포함). 나머지 영상은 A/B의 대조군으로 남긴다. | 목록 파일 |
| 2-2 태깅 실행 | 배치 러너로 실행. 소요 추정 = 영상당 약 4분 ÷ 병렬 수(쿼터에 좌우됨). | `datas/pikk_data/` |
| 2-3 컷 컬렉션 적재 | `ad_cut_reference`: 문서(D2) + 메타데이터(`video_id`, `cut_index`, `narrative_role`, 태그별 bool, `confidence` 요약, 프로필의 세그먼트 키 `industry_category/product_category_norm/duration_bucket/…`, `image_path`). id `"{video_id}:cut_{cut:03d}"`. | 신규 `db/chromadb/importers/cut_tags.py` |
| 2-4 그래프 확장 | 노드·엣지 추가(D5), `campaign_graph.py`에 `--with-cuts` 적재 경로. `role_technique_frequency(role, industry?, product_category?, top_k)`에서 빈도·lift 계산. | `db/graph/schema.py`, `db/graph/importers/`, `db/graph/graph_query.py` |
| 2-5 검색 `where` 지원 | dense·BM25 양쪽 필터, 선택적 재정렬(D9). 기본 동작은 변경 없음. | `db/chromadb/search_query.py`, `hybrid_search.py` |
| 2-6 도구 3종 | `search_cuts`(역할·기법·세그먼트 필터 + 하이브리드, 결과에 태그·근거 요약·키프레임 경로·부모 캠페인 요약), `search_technique_pattern`, `list_cut_vocab`. 로그는 기존 `_log_call` 재사용. | `db/chromadb/tool_definitions.py`, `server/mcp_server.py`, `db/chromadb/mcp_server.py` |
| 2-7 에이전트 연동 | `tools.py`의 `TOOL_FUNCS`/`TOOL_SPECS`에 추가(enum은 `list_cut_vocab` 응답 기반으로 시작 시 1회 로드), `RAG_USAGE_RULES`에 사용 규칙 추가, **`--cut-tools` 플래그**로 on/off. `scenario_agent_claude`(Claude Code 버전)는 MCP로 자동 노출되므로 프롬프트만 동기화(두 구현의 프롬프트 계약이 같아야 함). | `scenario_agent_claude_litellm/{tools,prompts,cli}.py`, `scenario_agent_claude/prompts.py` |
| 2-8 문서 | CLAUDE.md 규칙대로 같은 커밋에 갱신: `server/MCP_SPEC.md`, `docs/rag/rag_server_info.md`, `db/README.md`, `pikk_tagging/README.md`, 에이전트 README. | 문서들 |

**게이트 G2**: 도구가 서버에서 동작하고(스모크 테스트) 필터 결과가 골든 컷과 일치하며, 파일럿 영상에서 role×기법 통계가 정상(빈 결과·오류 없음)이고, 서버 메모리·기동 시간이 허용 범위.

### Step 3 — 실제 에이전트 A/B 실험

- **설계**: 제품 브리프 10~20개(파일럿 카테고리와 그 밖의 카테고리를 섞어 일반화 확인) × 2 조건(기존 5도구 vs `--cut-tools`) × 반복 2회. 모델·프롬프트(도구 규칙 제외)·예산 동일. 시작은 10 브리프 × 2 × 2 = 40회 실행. 비용은 README의 추정 단가 기준이라 실제 게이트웨이 청구액과 다를 수 있으므로 첫 5회로 실측 후 조정.
- **지표**
  1. 자동: 스키마·검증기 통과율, repair 횟수, 도구별 호출 수, 토큰·비용·소요시간(`trace.json`).
  2. 태그 활용: 씬의 `camera_notes`/`visual_effects`가 검색된 기법을 반영한 비율(사람이 표본 확인).
  3. 품질: 무작위 순서·조건 가림(블라인드) 쌍별 비교, 검수자 2인 이상. **주의**: 기존 `evaluation/scenario_checklist.md`는 분석용 `scenario_analysis.json` 형식 대상이고 에이전트의 `Scenario` 스키마와 다르다. 재사용 가능 여부(어댑터 필요 여부)를 착수 전 확인하고, 안 되면 새 루브릭을 만든다.
- **검색 단독 평가**: 브리프에서 파생한 질의 약 50개에 대해 관련 컷을 검수자가 지정 → recall@10, nDCG@10. 제거 실험 순서: dense → hybrid → +필터 → +재정렬 → +그래프 통계. 실제 질의는 서버 로그(`logs/search_chromadb/*`)에서 수집(서버 운영자에게 요청 필요).

**게이트 G3 (제안 기준)**: 블라인드 선호도에서 `--cut-tools` 조건이 우세(예: 60% 이상)하고, 검증 통과율이 나빠지지 않으며, 비용·시간 증가가 합의한 한도 이내. 이득이 없으면 어떤 구성요소(필터/통계/재정렬)가 기여하지 않았는지 제거 실험으로 확인하고 Step 4로 가지 않는다.

### Step 4 — 전체(약 502영상) 확장

| 작업 | 내용 |
|---|---|
| 4-1 대량 태깅 | 배치 러너로 전체 실행. 33시간(순차 추정)을 병렬·`--passes`·재검증 조정으로 단축하되, 정밀도를 낮추는 설정은 골든셋 회귀로 영향 확인 후 결정. 진행률·실패 재시도·비용 로그. |
| 4-2 적재 자동화 | 컷 컬렉션·그래프 재적재 명령을 한 줄로(`--rebuild` 포함). 태그 문서에 `vocab_version` 기록, 어휘 변경 시 재태깅 범위 규칙 정의(전체 vs 영향받은 태그만). |
| 4-3 품질 모니터링 | `stats.py`로 태그별 비율 드리프트 점검, 영상 표본 재검수 주기, 검증 실패·파싱 실패율 대시보드(로그 요약). |
| 4-4 서버 배포 | 내부망 서버(`10.110.56.157:8765`) 재배포·롤백 절차, 임베딩·재정렬 모델 메모리 확인. 운영자 협의 필요. |
| 4-5 후속(보류) | `Scene.technique_tags` 선택 필드 추가는 **에이전트·검증기·렌더러가 공유하는 계약 변경**이라 G3 통과 후 별도 결정. 컷 설명 문장 LLM 생성, 자유 태그 층(통제된 열린 층)도 여기서 검토. |

## 5. 변경 대상 파일 요약

| 저장소 | 파일 | 변경 |
|---|---|---|
| ad_video_analysis | `pikk_tagging/{vocab.json,prompts.py,schema.py,tagger.py}` | 역할 축, 정의 보강 |
| | `pikk_tagging/batch.py`(신규) | 병렬 배치 러너 |
| | `db/chromadb/importers/cut_tags.py`(신규) | 컷 컬렉션 적재 |
| | `db/chromadb/{search_query,hybrid_search}.py` | `where`·선택적 재정렬 |
| | `db/chromadb/tool_definitions.py`, `server/mcp_server.py`, `db/chromadb/mcp_server.py` | 도구 3종 |
| | `db/graph/{schema,graph_query}.py`, `db/graph/importers/campaign_graph.py` | Cut/Technique 노드, 통계 질의 |
| | `server/MCP_SPEC.md`, `db/README.md`, `pikk_tagging/README.md` | 문서 동기화 |
| aitive-Video-generation-agent | `scenario_agent_claude_litellm/{tools,prompts,cli}.py`, `scenario_agent_claude/prompts.py` | 도구·규칙·플래그 |
| | `docs/rag/rag_server_info.md` | 도구 문서 |

## 6. 리스크와 대응

| 리스크 | 대응 |
|---|---|
| 태그 오탐이 필터를 오염(타이포그래피 과다 등) | G1 게이트, D10 신뢰도 정책, 태그별 강등 |
| 컷 인덱스 불일치(전처리 재실행 시 컷 경계가 바뀜) | 컷은 `total/<id>/cuts.json`을 유일한 소스로 고정. 재전처리하면 태그·키프레임·CLIP 인덱스를 함께 재생성 |
| 기존 파이프라인 회귀 | D1·D5·D6(추가만, 수정 없음), 도구 플래그, 기존 컬렉션·그래프 미변경 |
| 서버 메모리·지연 증가(BM25 전체 로드, 재정렬 모델) | 재정렬은 옵션, A/B에서 지연 측정 후 결정 |
| 두 저장소 간 어휘·프롬프트 불일치 | D8(서버에서 어휘 수신), 프롬프트 동기화 체크리스트 |
| 참고 컷 그대로 베끼기(독창성·저작권) | 도구 응답에 원본 전체 대신 패턴 수준 요약을 기본으로 하고, 정책은 팀 합의 필요 |
| A/B 표본이 작아 결론이 불안정 | 반복 실행, 대조군 카테고리 포함, 정성 검수 병행 |
| LLM 비용 추정 오차(게이트웨이 청구 방식 미확인) | 첫 실행에서 실측, 예산 상한 유지 |

## 7. 결정이 필요한 사항 (착수 전 합의)

1. 게이트 G1·G3의 수치 기준(위는 제안일 뿐).
2. `lighting_tone` 축과 기존 `color_light_code`의 관계: 별개 유지 vs 매핑(중복 저장 방지).
3. 역할 소스 정책: pikk 직접 역할을 그래프의 기준으로 승격할지, `role_sequence`와 병행할지.
4. 골든셋 검수 인력·일정(검수자 2인 이상 필요).
5. 서버 재배포·로그 접근 담당자.
6. 시나리오 품질 평가 루브릭 확정(2.6·Step 3 주의 참고).
7. 대량 태깅에 사용할 모델과 예산(현재 `gemini-2.5-flash-lite`).

## 8. 이 계획서가 확인하지 못한 것

읽은 범위: `server/mcp_server.py`, `db/chromadb/{tool_definitions,search_query,hybrid_search,creative_search(일부),importers/production_reference,importers/keyframe_visual}.py`, `db/graph/*`, `evaluation/creative/element_schema.py`(일부), 에이전트 `tools.py/prompts.py/README`, `scenario_agent_claude/schema.py`, `docs/rag/rag_server_info.md`.
읽지 않은 것: `evaluation/scenario_eval/`, 에이전트의 `agent_loop.py`·`validators.py` 전문, `category_analysis`·`concept_reference` 적재 코드, ChromaDB 버전과 실제 컬렉션 내용, 서버 실행 환경. 이 중 D3(메타데이터 제약)와 `datas/total` ↔ 502 캠페인 일치 여부는 착수 시 첫 확인 항목이다.
