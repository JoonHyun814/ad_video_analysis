# evaluation/ad_concept_production

`scenario_analysis.json` 1건을 concept+production 양쪽으로 추출해 `ad_concept_reference`/
`ad_production_reference` 두 ChromaDB 컬렉션에 바로 적재하는 **단일 통합 파이프라인**이다.
[`../strategy/`](../strategy/README.md)(M1→M2→M3 3단계 순차 호출)+[`../concept/`](../concept/README.md)
+[`../creative/`](../creative/README.md) 를 CLI 3번으로 조합해야 했던 것을, 입력 1개 → LLM 호출
2건(concept 1회 + production 1회) → 적재까지 명령 1번으로 끝낸다.

기존 모듈과의 관계: 프롬프트는 이 모듈 전용으로 새로 작성했다(`strategy_extraction.py`/
`element_analysis.py` 를 호출하지 않는다). 다만 아래는 그대로 재사용한다 — 중복 유지가 산업별
enum 사전(29KB 설계 문서)까지 아우르므로 다시 베끼는 게 오히려 위험하다:

- `evaluation/creative/element_schema.py`/`subtypes_common.py`/`subtypes_packs.py` — element_type
  13종·subtype enum 사전(단일 출처)
- `evaluation/creative/element_analysis.py::compute_duration` — 시나리오 길이 계산 순수 함수
- `evaluation/creative/run.py::_industry_for` — `category_analysis.json` 기반 산업 판별
- `db/chromadb/importers/concept_reference.py::upsert_concept_reference` — `ad_concept_reference` 적재
- `db/chromadb/importers/production_reference.py::upsert_analysis` — `ad_production_reference` 적재

## 파일 구성

| 파일 | 역할 |
|------|------|
| `concept_prompt.py` | concept 추출 프롬프트(1회 호출) — `{"m1":{corejob,humantruth},"m2":{valueproposition},"m3":{concepts:[{lens,claimtag,bigidea,provingwhy,job,differentiation,risk}]}}` 반환. `db/chromadb/importers/concept_reference.py::upsert_concept_reference` 가 그대로 소비하는 모양 |
| `production_prompt.py` | production 추출 프롬프트(1회 호출) — `{"profile":{...},"casting":{...},"elements":[...]}` 반환. `db/chromadb/importers/production_reference.py::upsert_analysis` 가 그대로 소비하는 모양 |
| `pipeline.py` | `run_pipeline()` — scenario 로드 → 산업 판별 → 두 프롬프트 호출 → 결과 JSON 저장 → 두 컬렉션 upsert |
| `run.py` | CLI 실행기 (`python -m evaluation.cli --mode ad_concept_production`) |

## concept_prompt.py — 왜 1회 호출인가

`evaluation/strategy` 는 M1(corejob·humantruth·culturalcodes·marketscopes·target·forces·
triggers·opportunitytop3·assumptiontop3·verbatim) → M2(messagecandidates·positioningstatement·
valueproposition·ownedceps·topcompetitor·category·cepcoverage·demandspace·uniqueattributes) →
M3(seeds·fixedwhy·concepts, 발산 컨셉 다수 방지를 위해 순차 핸드오프) 3단계로 나뉘어 있다.
하지만 `ad_concept_reference` 문서·메타데이터가 실제로 쓰는 필드는 그중 일부뿐이다
(`corejob`·`humantruth.truth`·`humantruth.contradiction`·`valueproposition`·컨셉 1개의
`lens`·`bigidea`·`provingwhy`·`job`·`differentiation`·`claimtag`·`risk`) — 안 쓰는 필드까지
3단계로 순차 추론하면 지연시간·비용만 늘어난다. 그래서 필요한 필드만 남겨 1회 호출로
압축했다. 9개 전략 렌즈 풀·claimtag(C0/C1/C2) 정의는 `generation/v5_m0_m3/prompts/module3.md`
와 동일 어휘를 유지한다(임의로 새 렌즈를 만들지 않도록 프롬프트에 그대로 명시).

`m3.concepts` 는 정확히 1개만 요청한다(발산이 아니라 이미 만들어진 광고의 역추출이므로).

## production_prompt.py — 4개 축 분리

`element_schema.py` 의 `SINGLE_TYPES` 6종 중 `narrative_pattern`(구조 골격)·
`persuasion_engine`(무엇을 논증하는가, module5.md L2)·`narrative_form`(어떤 형식으로
전달하는가, L2.5)·`tone_register`(톤 반전 여부, L2.6) 는 서로 다른 4개 축이라 혼동하기
쉽다 — 프롬프트에 이 구분을 명시적으로 적어둔다(`_ELEMENT_AXIS_NOTE`).

## 실행

```bash
python -m evaluation.cli --mode ad_concept_production --video_id <ID> --data_dir <dir> [옵션]
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--video_id` | (필수) | 대상 영상 ID(쉼표 구분 복수 허용) |
| `--data_dir` | `output/total` | `<data_dir>/<video_id>/scenario_analysis.json` 입력(같은 폴더에 `category_analysis.json` 있으면 산업 판별에 사용, 없으면 `other`) |
| `--db_path` | (미지정 시 자동) | ChromaDB 저장 경로 — 안 주면 `ad_concept_reference`/`ad_production_reference` 가 각자 `data/<collection>/` 로 자동 결정된다(`db.chromadb.connection.db_path_for`) |
| `--llm_backend` | `claude` | `claude`(`claude -p` CLI, 로그인 세션 필요) \| `claude_api`(Anthropic API 직접 호출, `env/api.env` `ANTHROPIC_API_KEY` 필요) \| `codex` \| `gemini`(`env/api.env` `GEMINI_API_KEY` 필요) |
| `--timeout` | `600` | 추출 1건당 LLM 호출 타임아웃(초) |
| `--force` | off | `concept_analysis.json`/`production_analysis.json` 이 이미 있어도 무시하고 재추출(기본은 있으면 그 파일을 그대로 적재만 해 재실행 시 중복 과금을 막는다) |

```bash
python -m evaluation.cli --mode ad_concept_production --video_id 349 --data_dir output/total
```

출력 파일: `<data_dir>/<video_id>/concept_analysis.json`, `production_analysis.json`
(기존 `strategy_analysis.json`/`concept_evaluation.json`/`creative_element_analysis.json` 과는
별개 파일명 — 이 파이프라인 고유 산출물임을 구분한다).

저장소 루트 `rebuild_vector_db.py` 가 이 CLI 를 `data/ad_concept_production/<id>/` 폴더 구조로
배치 재구축할 때 쓴다(video_id 별 30분 간격, 세션 독립 백그라운드 프로세스).
