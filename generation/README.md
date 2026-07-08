# generation 모듈

신규 광고 브리프·시나리오를 생성한다. 단일 단계 (`--brief`, `--scenario`), 기존 M1~M7 파이프라인,
또는 새 CM1~CM4 컨셉 파이프라인(`--concept_pipeline`).

> **M1~M7 은 새 CM1~CM6 컨셉 파이프라인으로 대체될 예정이다.** 현재 CM1~CM4(카테고리 분석 →
> 타겟/포지셔닝 → 참고 광고 수집 → 컨셉 5개 생성)까지만 구현됐고, CM5(4점 채점·선정)·CM6(최종
> `scenario_analysis` 작성)이 없어 M1~M7 은 완성될 때까지 그대로 유지된다. CM 계열이 M5·M6 까지
> 갖춰지면 M1~M7 파일은 제거하고 `--pipeline` 이 CM 파이프라인을 가리키도록 전환한다.
> M4(비평·kill)·M6(레드팀 프리모템) 같은 적대적 검증 단계는 CM 파이프라인에서 의도적으로 뺐다 —
> 대신 CM5 가 `evaluation.concept_evaluation` 과 동일한 category·description·production_detail 정성 기준으로
> 컨셉을 직접 선정한다.

## 파일 구성

| 파일 | 역할 |
|------|------|
| `cli.py` | 진입점 (모드: `--brief` / `--scenario` / `--pipeline` / `--concept_pipeline` / `--stage`) |
| `brief_generator.py` | 웹 검색 기반 브리프 생성 |
| `web_searcher.py` | 검색 결과 수집 |
| `scenario_generator{,_codex,_gemini,_qwen}.py` | 단일 단계 시나리오 생성 (레거시) |
| `scenario_pipeline.py` | M1~M7 오케스트레이터 (`stage_path`/`save_json`/`load_json`/`llm_kwargs` 는 concept_pipeline 도 재사용) |
| `m1_consumer_insight.py` | M1 — 소비자 인사이트 |
| `m2_positioning.py` | M2 — 포지셔닝 전략 |
| `m3_concept_divergence.py` | M3 — 컨셉 발산 (5~8개) |
| `m4_concept_kill.py` | M4 — 컨셉 비평·킬 (GATE A) |
| `gates.py` | GATE A/B/C 판정 |
| `vector_reference.py` | M2 포지셔닝 → 유사 광고 조회, 컨셉별 유사도 검사/강제 kill (`video_category` 컬렉션) |
| `m5_dr_script.py` | M5 — DR 스크립트 (M6 피드백 재주입 지원) |
| `m6_red_team.py` | M6 — 레드팀 프리모템 |
| `m6_retry.py` | M6 GATE B 반송 후 자동 재진입 정책 (M5 재작성 / 컨셉 fallback) |
| `m7_validation.py` | M7 — 합성 사전스크린 + 인간 게이트 |
| `concept_pipeline.py` | CM1~CM4 오케스트레이터 |
| `m1_category_insight.py` | CM1 — 상품 특징·시장 반응 분석 → industry_category/product_category 결정 |
| `m2_target_positioning.py` | CM2 — 유사 상품 시장 분석 → target_persona/usp/positioning 결정 |
| `m3_reference_collection.py` | CM3 — `video_concept` 컬렉션에서 4개 관점으로 참고 광고 수집 (LLM 미사용) |
| `m4_concept_generation.py` | CM4 — 참고 광고 기반 컨셉 5개 생성 (평가·선정 없음) |

## M1~M7 단계 (레거시, 대체 예정)

| 모듈 | 내용 |
|------|------|
| M1 | 소비자 인사이트 추출 |
| M2 | 포지셔닝 전략 |
| M3 | 컨셉 발산 (5~8개) |
| M4 | 컨셉 비평·킬 (GATE A) |
| M5 | DR 스크립트 생성 |
| M6 | 레드팀 프리모템 |
| M7 | 합성 사전스크린 + 인간 게이트 |

## CM1~CM4 단계 (신규, 구현 중)

| 모듈 | 내용 |
|------|------|
| CM1 | 상품 특징·시장 반응 분석 → industry_category/product_category 결정 |
| CM2 | 유사 상품 시장 분석 → target_persona/usp/positioning 결정 |
| CM3 | `video_concept` 컬렉션에서 참고 광고 수집 — ① 전략 유사(같은 카테고리) ② 타겟·USP·포지셔닝 유사 ③ 소구 유형(appeal_type) 다각화 ④ 연출 스타일(execution_style) 다각화, 4개 관점 각각 별도 조회 후 병합 |
| CM4 | CM1~CM3 을 참고해 서로 다른 컨셉 5개 생성. 참고 광고는 모방 대상이 아니라 차별화 기준으로만 제시 |
| CM5 (미구현) | category·description·production_detail 정성 기준으로 컨셉 선정 |
| CM6 (미구현) | 선정 컨셉을 `scenario_analysis.json` 형태(세부 캐스팅·연출)로 작성 |

### CM3 참고 광고 조회 방식

| 관점 | 조회 방식 | 비고 |
|------|-----------|------|
| 전략 유사 | 임베딩 유사도 + `industry_category` exact 필터 | 카테고리 관행 파악용 |
| 타겟·USP·포지셔닝 유사 | 임베딩 유사도 (카테고리 필터 없음) | 페르소나가 겹치는 타 카테고리도 참고 가능 |
| 소구 유형 다각화 | `appeal_type` 값이 서로 다른 광고를 1건씩 표본 추출 | 같은 소구 유형만 반복 참고되지 않도록 다각화 |
| 연출 스타일 다각화 | `execution_style` 값이 서로 다른 광고를 1건씩 표본 추출 | 위와 동일 |

`video_concept` 컬렉션이 비어있으면 (아직 `evaluation.concept_cli --load_vector` 로 적재 전) 4개 관점 모두
빈 리스트로 채워지고 CM4 는 참고 광고 없이 생성한다 — 파이프라인은 중단되지 않는다.

## 사용법

```bash
python -m generation.cli --brand <브랜드> --product <제품> [모드] [옵션]
```

| 모드 | 동작 |
|------|------|
| `--brief` | 웹 검색 기반 브리프 생성 → `<brand>_<product>.json` |
| `--scenario` | 단일 단계 시나리오 생성 (레거시) |
| `--pipeline` | M1→M7 전체 자동 실행 |
| `--concept_pipeline` | CM1→CM4 전체 자동 실행 (CM5·CM6 미구현) |
| `--stage m1\|...\|m7\|cm1\|...\|cm4` | 특정 단계만 실행 (이전 단계 출력 필요) |

| 입력 옵션 (미입력 시 모델이 채움) | 설명 |
|------|------|
| `--usp`, `--target_age`, `--target_persona`, `--positioning`, `--slogan` | 텍스트 |
| `--ingredients`, `--functions` | 다중 값 (`--ingredients a b c`) |

| 공통 | 기본값 | 설명 |
|------|--------|------|
| `--llm_backend` | `claude` | `claude` \| `codex` \| `qwen` \| `gemini` |
| `--codex_model` / `--qwen_model` / `--gemini_model` | — | 백엔드별 모델명 |
| `--output_dir` | `output/generation` | 결과 저장 |

| 벡터 DB 참조 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--m3_reference` | off | [M3] M2 포지셔닝과 유사한 기존 광고를 검색해 발산 컨텍스트로 주입 |
| `--m3_reference_n` | `5` | [M3] 참고할 유사 광고 수 |
| `--m4_similarity_kill` | off | [M4] 컨셉별 기존 광고 유사도 검사, threshold 이내면 강제 kill |
| `--m4_similarity_threshold` | `0.30` | [M4] cosine distance 한계 — 작을수록 엄격, 코퍼스 보고 튜닝 (`db/chromadb_show.py`) |
| `--m5_narrative_reference` | off | [M5] 선정 컨셉의 서사 필드로 기존 광고를 검색해 스크립트 참고로 주입 (브랜드·산업 제외) |
| `--m5_narrative_reference_n` | `5` | [M5] 참고할 서사 유사 광고 수 |
| `--vector_db_path` | `output/vector_db` | ChromaDB 저장 경로 |
| `--vector_collection` | `video_category` | ChromaDB 컬렉션명 |

> `--m3_reference` / `--m4_similarity_kill` / `--m5_narrative_reference` 모두 `evaluation/category_cli.py --load_vector` 로 적재된 ChromaDB 컬렉션을 사용한다. 컬렉션이 비어있거나 조회에 실패하면 참고/검사가 생략된다 (파이프라인은 계속 진행).

| CM1~CM4 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--concept_collection` | `video_concept` | [CM3] `evaluation/concept_cli.py --load_vector` 로 적재된 컬렉션명 |
| `--concept_reference_n` | `5` | [CM3] 4개 관점(전략유사·타겟유사·소구다각화·연출다각화)마다 참고할 광고 수 |

> CM3 는 `--vector_db_path` (M1~M7 과 공유) + `--concept_collection` 을 사용한다. 컬렉션이 비어있거나
> 조회에 실패하면 해당 관점만 빈 리스트로 채워지고 CM4 로 계속 진행한다.
>
> **M3 vs M5 의 검색 의도 차이** — M3 는 *포지셔닝* 유사(브랜드·산업·USP 포함)로 "비슷한 광고와 다른 방향" 발산을 유도하고, M5 는 *서사* 유사(`narrative_structure` / `hook_strategy` / `creative_style` / `key_message` 만)로 "브랜드와 무관하게 서사를 어떻게 풀어갔는지" 만 학습 자료로 쓴다.

| M6 자동 재진입 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--m6_auto_retry_max` | `0` | GATE B 반송 시 자동 재진입 최대 횟수 (0 = 비활성). M6 verdict 와 `unresolved_criticals` 에 따라 M5 재작성 또는 M4 컨셉 fallback 으로 분기. |

> **재진입 정책** (`m6_retry.py`)
> 1. `unresolved_criticals` 가 비어있지 않거나 `verdict == return_to_gate_a` → **컨셉 fallback**: `m4.selected` 의 다음 후보(`selected[1]`)로 전환하고, 떨어진 컨셉은 `killed` 에도 추가(감사 추적 유지). selected 가 1개뿐이면 중단.
> 2. `verdict == return_to_m5` 이고 1번 조건이 아니면 → **M5 재작성**: 직전 M6 `failure_modes`/`mitigation` 을 M5 프롬프트에 주입해 스크립트만 재생성 (l0~l2 골격 유지).
> 3. 그 외 verdict (`kill` / `return_to_phase1` / `proceed`) → 중단.
> 4. 매 시도마다 새 M6 가 다시 평가하며, `max` 도달 또는 위 조건으로 중단되면 마지막 M6 결과로 GATE B 가 한 번 더 판정된다.
> 5. 재시도 피드백은 **누적이 아닌 교체**다 — 매번 직전 M6 만 주입해 프롬프트 비대화를 방지한다. **컨셉 fallback 분기에서는 피드백을 주입하지 않는다** (이전 컨셉의 실패 서술이 새 컨셉에 부적절한 mitigation 을 유도하므로).
>
> **재시도 결과 보존** — 첫 시도(attempt=1) 결과는 기본 경로(`<brand>_<product>_m5.json` 등)에 저장되고, 1번째 재시도부터는 `_<attempt>.json` 으로 분리 저장돼 직전 결과를 덮어쓰지 않는다.
> - 1번째 재시도: `_m4_2.json` (swap 시) · `_m5_2.json` · `_m6_2.json`
> - 2번째 재시도: `_m5_3.json` · `_m6_3.json`
> - 다운스트림(M7) 은 메모리에 보존된 최신 m5/m6 을 사용한다. `--stage m7` 단독 재실행 경로는 기본 파일(`_m5.json` = 첫 시도) 을 읽으므로, 재시도 결과로 M7 을 돌리려면 풀 파이프라인 모드로 재실행해야 한다.

## 예시

```bash
# 풀 파이프라인 (M1~M7)
python -m generation.cli --brand 설화수 --product 윤조에센스 --pipeline --llm_backend gemini

# 단일 단계 재실행 (M3 만, 이전 M1·M2 출력 필요)
python -m generation.cli --brand 설화수 --product 윤조에센스 --stage m3

# 웹 검색 브리프만 생성
python -m generation.cli --brand 설화수 --product 윤조에센스 --brief

# 새 CM1~CM4 컨셉 파이프라인 (video_concept 컬렉션은 evaluation.concept_cli --load_vector 로 사전 적재)
python -m generation.cli --brand 설화수 --product 윤조에센스 --concept_pipeline

# CM 단일 단계 재실행 (CM3 만, 이전 CM1·CM2 출력 필요)
python -m generation.cli --brand 설화수 --product 윤조에센스 --stage cm3

# 벡터 DB 참조 켠 풀 파이프라인 (M3 발산 참고 + M4 유사도 kill + M5 서사 참고)
python -m generation.cli --brand 설화수 --product 윤조에센스 --pipeline \
    --m3_reference --m3_reference_n 5 \
    --m4_similarity_kill --m4_similarity_threshold 0.25 \
    --m5_narrative_reference --m5_narrative_reference_n 5

# M6 게이트 반송 시 최대 2회 자동 재진입 (스크립트 재작성 또는 컨셉 fallback)
python -m generation.cli --brand 맥도날드 --product 스리라차마요 --pipeline \
    --m3_reference --m4_similarity_kill --m5_narrative_reference \
    --m6_auto_retry_max 2
```

## 출력 파일명

`<output_dir>/<brand>_<product>.json` — 브리프
`<output_dir>/<brand>_<product>_<stage>.json` — M1~M7 각 단계, CM1~CM4 는 `<stage>` 에 `cm1`~`cm4` 사용
(M1~M7 파일명과 겹치지 않으므로 같은 `--output_dir` 에서 두 파이프라인을 함께 실행해도 서로 덮어쓰지 않는다)
