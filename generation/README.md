# generation 모듈

클리셰 인지(cliché-aware) 광고 생성 파이프라인 G1~G6.

> **v5_m0_m3/**: 이 파이프라인과 별개로, `shortform-pipeline-master_test` 프로젝트의
> DR-CTV v5 MODULE 0~9(소재 인제스트→인사이트→포지셔닝→컨셉 발산→비평·킬→스크립트→
> 레드팀→검증→콘티, M8 은 원본에도 결번)를 이식한 독립 서브패키지가 `generation/v5_m0_m3/`
> 에 있다. G1~G6 와 서로 참조하지 않으며, M0~M3 와 M4~M9 를 각각 따로 실행할 수 있다.
> 자세한 내용은 [`v5_m0_m3/README.md`](v5_m0_m3/README.md) 참고.

> **story_bard/**: `story_board` 프로젝트를 이식한 독립 도구가 `generation/story_bard/`
> 에 있다. 스토리보드 자리표시자 HTML을 Codex CLI로 완성 비주얼(이미지 생성·삽입·렌더링)로
> 바꾸고, 이어서 Seedance 2.0(image-to-video) 핸드오프용 `storyboard-grid.png`·`prompt.txt`
> 까지 생성하는 후처리 단계로, G1~G6·v5_m0_m3 와 서로 참조하지 않는다. 자세한 내용은
> [`story_bard/README.md`](story_bard/README.md) 참고.

> **retrieval_pipeline/**: 한 줄 크리에이티브 원칙("기기를 보여주지 말고 ~ 을 보여라" 같은)을
> 입력받아 자사 광고 벡터 DB 검색 근거로 `docs/DBH_Creative_Reference_Ideas.md` 형식의 연출
> 레퍼런스 문서를 만드는 파이프라인이 `generation/retrieval_pipeline/` 에 있다. M0~M2 는
> `v5_m0_m3` 로직을 그대로 재사용하고(서로 참조하지 않는 G1~G6/story_bard 와 달리, 이 파이프라인은
> M0~M2·LLM 어댑터를 v5_m0_m3 에서 재사용한다), M3 는 아직 공백 placeholder다. 자세한 내용은
> [`retrieval_pipeline/README.md`](retrieval_pipeline/README.md) 참고.

광고주가 장르/타겟/USP 를 지정하면, facet 벡터 DB(`ad_target`/`ad_usp`/`ad_creative`)에서
같은 세그먼트의 기존 광고 분포를 분석해 **클리셰를 따를지(follow)/피할지(avoid)/비틀지(subvert)** 를
결정하고, 그 결정을 준수하는 컨셉·시나리오를 생성한다.

> 이전 M1~M7·CM1~CM4 파이프라인은 제거됐다. facet 컬렉션 적재는
> `python -m evaluation.cli --mode concept --load_facets`
> ([`../evaluation/concept/README.md`](../evaluation/concept/README.md)) 또는
> [`../db/README.md`](../db/README.md) 의 `db/load_facets.py` 참고.

## 파일 구성

| 파일 | 역할 | LLM |
|------|------|-----|
| `cli.py` | 진입점 (`--brief` / `--pipeline` / `--stage g1~g6`) | — |
| `pipeline.py` | G1~G6 오케스트레이터 (`stage_path`/`save_json`/`load_json`/컨셉 선정) | — |
| `g1_input_normalization.py` | G1 — 광고주 입력을 enum + facet 텍스트로 정규화 | ○ |
| `segment_retrieval.py` | G2ⓐ — 세그먼트 추출 (exact 필터 → 계층 완화 → facet RRF 랭킹) | ✕ |
| `cliche_report.py` | G2ⓑ — 분포 히스토그램 + K-Means 군집으로 클리셰 리포트 생성 | ✕ |
| `g3_cliche_decision.py` | G3 — 패턴별 follow/avoid/subvert 결정 | ○ |
| `g4_concept_generation.py` | G4 — 결정을 준수하는 컨셉 5개 생성 | ○ |
| `g5_verification.py` | G5 — 컨셉 임베딩 ↔ 클리셰 클러스터 centroid 거리 검증 | ✕ |
| `g6_scenario_writer.py` | G6 — 선정 컨셉을 `scenario_analysis` 스키마 시나리오로 작성 | ○ |
| `brief_generator.py` | 웹 검색 기반 브리프 생성 | ○ |
| `web_searcher.py` | 검색 결과 수집 | — |

## G1~G6 단계

| 단계 | 내용 | 출력 핵심 필드 |
|------|------|----------------|
| G1 | 광고주 입력(자유 텍스트) 정규화. 지정값은 의미 유지, 빈 항목은 브리프에서 추론 | `genre`(enum)·`industry_category`·`target_persona`·`usp`·`brand_position` |
| G2 | 세그먼트 추출 + 클리셰 리포트. `장르+산업` exact → `산업` → `장르` → `전체` 순 계층 완화, 타겟/USP facet 유사도 RRF 랭킹. 속성 분포를 `category_codes`(점유율≥0.75 관행) / `creative_cliches`(≥0.40 과밀) / `whitespace`(미사용) 로 분류, 크리에이티브 임베딩 K-Means 로 밀집 클러스터 탐지 | `segment.relax_level`·`report.histograms`·`report.clusters` |
| G3 | 리포트 패턴별 follow/avoid/subvert 결정. category_code 는 제품 이해 장치(기본 follow), creative_cliche 는 차별화 기회(기본 avoid/subvert) — `brand_position`·표본 신뢰도(n, relax_level)를 판단에 반영 | `decisions[]`·`whitespace_picks[]`·`creative_direction` |
| G4 | 결정을 준수하는 서로 다른 컨셉 5개 생성. `creative_summary` 는 G5 임베딩 검증용 서술 | `concepts[].creative_summary`·`applied_decisions` |
| G5 | 각 컨셉의 creative_summary 를 bge-m3 로 임베딩해 avoid/subvert 클러스터 centroid 와의 cosine distance 실측. threshold 이내 근접 시 violation | `results[].cluster_checks`·`passed[]` |
| G6 | 선정 컨셉(G5 통과 첫 컨셉 또는 `--concept_id`)을 분석 파이프라인과 동일한 `scenario_analysis` 스키마로 작성 → 기존 평가·적재 도구에 그대로 통과 가능 | `scenes[].beats`·`production_notes` |

## 사용법

```bash
python -m generation.cli --brand <브랜드> --product <제품> [모드] [옵션]
```

| 모드 | 동작 |
|------|------|
| `--brief` | 웹 검색 기반 브리프 생성 → `<brand>_<product>.json` |
| `--pipeline` | G1→G6 전체 자동 실행 |
| `--stage g1\|...\|g6` | 특정 단계만 실행 (이전 단계 출력 필요) |

브리프 소스: `--brief` 지정 시 웹 검색, 기존 `<brand>_<product>.json` 있으면 재사용, 없으면 CLI 입력값으로 seed 브리프 구성.

| 광고주 지정값 (미입력 시 G1 이 추론) | 설명 |
|------|------|
| `--genre` | 광고 장르 — 자유 텍스트 또는 enum(`humor\|emotional\|informational\|aspirational\|urgency\|other`) |
| `--target_persona`, `--usp`, `--positioning` | 타겟/차별화/포지셔닝 서술 |
| `--brand_position` | `leader\|challenger\|new_entrant` — G3 follow/avoid 판단에 사용 |
| `--target_age`, `--slogan`, `--ingredients`, `--functions` | 브리프 생성용 |

| 세그먼트/클리셰 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--vector_db_path` | `output/vector_db` | ChromaDB 경로 (facet 컬렉션 3개 필요) |
| `--min_segment` | `15` | [G2] 세그먼트 최소 표본 — 미달 시 필터 계층 완화 |
| `--segment_cap` | `60` | [G2] 세그먼트 최대 멤버 수 |
| `--code_share` | `0.75` | [G2] category_code 분류 점유율 컷 |
| `--cliche_share` | `0.40` | [G2] creative_cliche 분류 점유율 컷 |
| `--cluster_seed` | `42` | [G2] K-Means 시드 |
| `--avoid_distance` | `0.35` | [G5] avoid/subvert 클러스터와의 최소 cosine distance — 코퍼스 보고 튜닝 |

| 기타 | 기본값 | 설명 |
|------|--------|------|
| `--duration` | `30.0` | [G6] 영상 길이(초) |
| `--concept_id` | — | [G6] 확장할 컨셉 ID (기본: G5 통과 첫 컨셉) |
| `--llm_backend` | `claude` | `claude` \| `codex` \| `gemini` |
| `--codex_model` / `--gemini_model` | — | 백엔드별 모델명 |
| `--output_dir` | `output/generation` | 결과 저장 |

## 예시

```bash
# 사전 준비 (1회): facet 컬렉션 적재
python db/load_facets.py --data_root output/total

# 광고주 지정값과 함께 풀 파이프라인
python -m generation.cli --brand 설화수 --product 윤조에센스 --pipeline \
    --genre emotional --target_persona "40대 여성, 안티에이징 관심" --usp "발효 성분" \
    --brand_position leader

# 웹 검색 브리프 생성 후 파이프라인 (브리프 파일 재사용)
python -m generation.cli --brand 설화수 --product 윤조에센스 --brief
python -m generation.cli --brand 설화수 --product 윤조에센스 --pipeline

# G3 결정만 재실행 (G1·G2 출력 필요)
python -m generation.cli --brand 설화수 --product 윤조에센스 --stage g3

# 특정 컨셉으로 15초 시나리오 작성
python -m generation.cli --brand 설화수 --product 윤조에센스 --stage g6 \
    --concept_id C3 --duration 15
```

## 출력 파일명

- `<output_dir>/<brand>_<product>.json` — 브리프
- `<output_dir>/<brand>_<product>_g1.json` ~ `_g6.json` — 각 단계 결과
- `_g2.json` 은 `{"segment": ..., "report": ...}`, `_g6.json` 은 `scenario_analysis` 스키마

## 클리셰 판단 로직 요약

- **세그먼트 축**(장르·산업·타겟·USP)은 필터/유사도 매칭용, **크리에이티브 축**(소구·연출·서사)은 분포 측정용 — facet 컬렉션 분리로 두 축을 구분한다.
- 점유율이 매우 높은 패턴(category_code)은 "이 카테고리 광고로 읽히게 하는 장치"라 따르는 게 안전한 경우가 많고, 과밀 소구·연출(creative_cliche)이 차별화 기회다.
- 표본이 작으면(`relax_level` 완화, 낮은 `n`) 결정 강도를 낮추도록 G3 프롬프트에서 강제한다.
- G5 는 "피하겠다"는 선언이 실제 임베딩 공간에서 지켜졌는지 실측한다 — 선언만 하고 클리셰 클러스터 중심에 근접한 컨셉은 violation.
