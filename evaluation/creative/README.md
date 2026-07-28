# evaluation/creative

클리셰 분석 파이프라인 — [`creative_element_schema.md`](creative_element_schema.md) 설계 문서의 구현 (v2).

`scenario_analysis.json` 에서 크리에이티브 요소(오프닝 훅, 인물 연출, 감각 시연, 신뢰 장치,
제품 컷, 색·조명, 카피 장치, 서사, 사운드, CTA)를 enum 으로 추출해 벡터 DB 에 적재하고,
세그먼트(예: beauty×스킨케어×15초) 내 빈도 집계로 클리셰/클리셰 파괴 요소를 판정한다.

핵심 원칙 두 가지:

- **클리셰 여부는 적재 시점에 판정하지 않는다** — DB 에는 중립적 요소만 저장하고,
  판정은 리포트 시점에 세그먼트 상대 빈도로 계산한다 (코퍼스가 바뀌면 판정도 바뀐다).
- **(v2) element_type 10종은 전 산업 공통, subtype 은 공용 사전 + 산업 팩 병합** —
  추출 시 `category_analysis.json` 의 industry_category 로 팩(beauty/tech_electronics/entertainment/
  fashion_apparel/health_medical/food_beverage/household_care)을 선택한다. 산업 관통 클리셰는 type/공용 subtype 레벨에서 교차 비교된다.
  `household_care`(생활용품: 세정살균티슈·섬유유연제·세제부스터)는 category_analysis.json 상 `retail_ecommerce`/`other`
  로 흩어져 있어 자동 별칭을 두지 않았다 — 두 값이 이 산업 외에도 쓰이는 catch-all 이라 `--industry_secondary` 로 수동 지정한다.
- **`product_shot` 도 `NONE_TYPES` 에 포함** — 무형 서비스(플랫폼 서비스 등) 광고는 제품 실물 샷이
  없을 수 있어 `none` 레코드로 의도적 생략을 기록한다.
- **부산업(`industry_secondary`) 지원** — 다트비트(스마트 홈다트)처럼 tech_electronics(하드웨어)+
  entertainment(대전·토너먼트) 양쪽 문법이 섞인 광고는 두 산업 팩이 함께 프롬프트에 제시되고,
  `--industry` 리포트 필터가 주산업·부산업 어느 쪽으로도 매칭한다 (`$or` 쿼리).
  `product_category_norm` 은 주산업 enum 값 하나로 유지된다 — 콤마 결합하지 않는다
  (ChromaDB 메타데이터는 `$eq` exact match 전제라, 다중값을 콤마 문자열로 넣으면 필터가 깨진다).

## 파일 구성

| 파일 | 역할 |
|------|------|
| `run.py` | CLI 실행기 (`python -m evaluation.cli --mode creative`) |
| `element_schema.py` | element_type 10종·profile/casting enum·산업별 카테고리 enum·legacy 매핑 |
| `subtypes_common.py` | 전 산업 공용 subtype 사전 |
| `subtypes_packs.py` | 산업별 subtype 확장 팩 (beauty / tech_electronics / entertainment / fashion_apparel / health_medical / food_beverage / household_care) |
| `element_analysis.py` | LLM 추출 (claude) — 시나리오+산업 팩 → `creative_element_analysis.json` |
| `element_vector_store.py` | 컬렉션 2개 upsert/조회 + v1 파일 legacy 정규화 |
| `cliche_aggregate.py` | 세그먼트 빈도 집계 + 판정 (strong_cliche/convention/minor/cliche_breaker) |
| `reference_retrieval.py` | 크리에이티브 벡터 DB에서 참조 광고를 의미 유사도로 검색하는 서비스 함수(`search_reference_ads`/`list_segment_columns`). MCP 서버와 `generation/v5_m0_m3` 의 Anthropic tool_use 경로가 공유한다 |
| `mcp_server.py` | 위 함수를 FastMCP 도구로 노출하는 stdio MCP 서버(`creative-retrieval`). 저장소 루트 `.mcp.json`/`.claude/settings.json` 이 등록·승인을 담당 |

## 컬렉션

| 컬렉션 | 단위 | 용도 |
|--------|------|------|
| `video_creative_profile` | 영상 1개 = 1레코드 | 세그먼트 검색. 메타데이터에 `industry_category`+정규화 필터 키+캐스팅 속성 |
| `ad_creative_element` | 요소 1개 = 1레코드 | 클리셰 빈도 집계. 세그먼트 필터 키를 요소 메타데이터에 복제 |

판정 기준: 세그먼트 내 빈도 ≥60% → `strong_cliche`, 30~60% → `convention`,
1편 고립(n≥3) → `cliche_breaker`, 그 외 `minor`.

v1 분석 파일(`texture_shot`/`model_direction`/`clinical_spec_number` 등)은 적재 시
`LEGACY_*_MAP` 으로 자동 변환되므로 재추출 없이 `--load_vector` 만 다시 실행하면 된다.
usp/positioning 미기재 파일은 같은 폴더의 `concept_evaluation.json` 대표값으로 백필된다
(`price_tier` 는 재추출 시에만 채워짐).

## 실행

```bash
python -m evaluation.cli --mode creative [--extract] [--load_vector] [--report] [옵션]
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--video_id` | — | 대상 영상 ID. 쉼표 구분 복수 허용 (`343,348,325`) |
| `--data_dir` | `output/total` | `<data_dir>/<video_id>/scenario_analysis.json` 입력 (industry 는 같은 폴더의 `category_analysis.json` 에서 판별. `fashion`→`fashion_apparel`, `healthcare`→`health_medical` 등 어휘 차이는 `run.py::_CATEGORY_INDUSTRY_ALIAS` 로 흡수) |
| `--extract` | off | 요소 추출 → `creative_element_analysis.json` |
| `--industry_secondary` | — | [extract] 부산업 강제 지정 (예: `entertainment`). 배치 전체 동일 적용. 미지정 시 `category_analysis.json` 의 `industry_category` 가 리스트면 2번째 값을 자동 사용 |
| `--load_vector` | off | 추출 결과를 컬렉션 2개에 upsert (v1 파일 자동 변환) |
| `--report` | off | 세그먼트 클리셰 리포트 출력 |
| `--db_path` | `output/vector_db` | ChromaDB 저장 경로 |
| `--industry` | — | [report] `industry_category` 필터 (예: `beauty`, `tech_electronics`) |
| `--product_category` | — | [report] `product_category_norm` 필터 (예: `skincare`) |
| `--product_subtype` / `--target_gender` / `--duration_bucket` | — | [report] 추가 세그먼트 필터 |
| `--usp` / `--positioning` / `--price_tier` | — | [report] 제품 차별성 필터 (usp_category / positioning_category / price_tier) |
| `--out` | — | [report] 리포트 JSON 저장 경로 |

```bash
# 추출 + 적재 (industry 팩 자동 선택)
python -m evaluation.cli --mode creative --extract --load_vector \
    --video_id 42,57,78 --data_dir ../output/total

# beauty 스킨케어 15초 세그먼트 클리셰 리포트
python -m evaluation.cli --mode creative --report \
    --industry beauty --product_category skincare --duration_bucket 15s \
    --out output/cliche_report_skincare_15s.json

# tech 15초 세그먼트 리포트
python -m evaluation.cli --mode creative --report --industry tech_electronics --duration_bucket 15s
```

## MCP 서버 — 참조 광고 검색 도구

`video_creative_profile`/`ad_creative_element` 두 컬렉션을 `creative-retrieval` 라는 이름의
MCP 서버로 노출한다(저장소 최초의 MCP 서버). 도구 2개:

| 도구 | 인자 | 반환 |
|------|------|------|
| `list_segment_columns` | 없음 | `{"columns": {...}, "note": ...}` — `columns` 는 필터 가능한 세그먼트 컬럼과 각 컬럼의 허용 값(`reference_retrieval.SEGMENT_COLUMNS`, `element_schema.py` enum 에서 파생), `note` 는 이 값들이 오타·의역 불가한 정확 일치(exact-match) enum 이며 맞는 값이 없으면 `segment_column`/`segment_value` 를 생략하고 `query_text` 자연어 검색만 쓰라는 안내문 |
| `search_reference_ads` | `query_text`(필수, 자연어), `segment_column`/`segment_value`(선택, `list_segment_columns` 가 준 값과 정확히 일치해야 함 — 특히 `_norm` 이 붙은 컬럼은 표준화된 고정 enum), `top_k`(기본 5, 최대 20) | `query_text` 의미 유사도로 정렬된 참조 광고 목록. 각 항목에 대표 크리에이티브 요소(`notable_elements`, 최대 4개)도 첨부. 세그먼트 필터를 걸었는데 0건이면 "enum 값은 유효하나 적재된 데이터 없음" 안내(`note`)를 함께 반환 |

`generation/v5_m0_m3` 파이프라인이 `--retrieval` 옵션으로 이 도구를 M1~M3 LLM 호출에 연결한다
(자세한 내용은 [`../../generation/v5_m0_m3/README.md`](../../generation/v5_m0_m3/README.md)) — 어떤
컬럼/값으로 몇 건을 검색할지는 LLM 이 그때그때 판단하되, `segment_value` 는 `list_segment_columns`
가 반환한 값 그대로만 써야 하고(추측·의역 금지), 맞는 값이 없으면 `query_text` 자연어 검색으로
대체하도록 도구 설명에 명시돼 있다.

**호출 로깅(선택)**: 환경변수 `REFERENCE_RETRIEVAL_LOG_PATH`(필수) + `REFERENCE_RETRIEVAL_LOG_STAGE`
(선택, "누가 호출했는지" 태그)를 지정하면 두 도구 호출마다 그 경로에 JSONL 로 1줄씩 append 된다
(`reference_retrieval._log_call`). MCP(별도 서브프로세스) 경유든 같은 프로세스 안에서 함수를
직접 부르든 이 두 환경변수만 맞으면 동일하게 기록된다 — `generation/v5_m0_m3` 는 이 메커니즘을
`--retrieval` 사용 기록(`<slug>_retrieval.jsonl`)에 그대로 쓴다. 미지정 시 로깅 없음(기본).

**임베딩 모델 예열**: `mcp_server.py` 는 `__main__` 실행 시 `reference_retrieval.warm_up()` 으로
bge-m3 임베딩 모델을 서버 기동 시점에 미리 로드한다 — 그렇지 않으면 첫 `search_reference_ads`
호출이 모델 로딩 비용(수십 초, 기기 부하에 따라 더 걸릴 수 있음)까지 떠안아 `claude -p` 쪽
도구 호출이 느려 보이거나 타임아웃에 걸릴 수 있다.

로컬에서 직접 실행/디버그:
```bash
python -m evaluation.creative.mcp_server
```

등록: 저장소 루트 `.mcp.json`(서버 명령, 커밋됨). `claude -p` 헤드리스 호출로 이 서버를 쓰려면
(`generation/v5_m0_m3 --retrieval --llm_backend cli`) 추가 승인이 필요하다 — `.claude/` 는
`.gitignore` 로 전부 제외되는 개인 로컬 상태라 승인 자체는 저장소에 커밋되지 않는다. 로컬에
`.claude/settings.json` 을 만들어 `{"enabledMcpjsonServers": ["creative-retrieval"]}` 를 넣거나,
프로젝트 디렉터리에서 `claude` 를 한 번 대화형으로 실행해 승인한다(1회). Anthropic API 직접
tool_use 경로(`--llm_backend api`)는 이 승인 절차가 필요 없다.

## 향후 확장 (설계 문서 참고)

- `other`/`description` 임베딩 K-Means 군집화로 enum 에 없는 신규 클리셰 발견
- `creative_dedup_key` 기반 동일 소재 지면 변형 자동 중복 제거
