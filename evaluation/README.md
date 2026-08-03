# evaluation 모듈

시나리오 평가 + 카테고리/컨셉 메타데이터 추출 + 벡터 DB 적재 + 스키마 변환.

## 폴더 구성

| 폴더 | 역할 | 상세 문서 |
|------|------|-----------|
| `brief/` | scenario_analysis → 브리프 추출 | [brief/README.md](brief/README.md) |
| `parsed/` | 파이프라인 산출물 종합 → parsed_analysis | [parsed/README.md](parsed/README.md) |
| `scenario_eval/` | 시나리오 평가 (브리프 비교 포함/제외) | [scenario_eval/README.md](scenario_eval/README.md) |
| `category/` | 카테고리 메타데이터 추출 + `video_category` 벡터 적재 | [category/README.md](category/README.md) |
| `concept/` | 컨셉 추출 + `video_concept`/facet 벡터 적재 | [concept/README.md](concept/README.md) |
| `creative/` | 크리에이티브 요소 추출 + 클리셰 리포트 | [creative/README.md](creative/README.md) |
| `strategy/` | M1·M2·M3 전략 스키마 역추출 | [strategy/README.md](strategy/README.md) |
| `convert/` | 외부 시스템 스키마 변환·재명명 | [convert/README.md](convert/README.md) |

루트 파일:

| 파일 | 역할 |
|------|------|
| `cli.py` | 통합 CLI 진입점 (`--mode` 로 하위 파이프라인 디스패치) |
| `schemas.py` | 브리프/평가 공용 JSON 스키마 정의 |
| `scenario_checklist.md` | 시나리오 평가 체크리스트 |
| `docs/m1.txt`·`docs/m2.txt`·`docs/m3.txt` | 영상 생성용 M1~M3 원본 프롬프트 (strategy 역추출 스키마의 출처) |

## 통합 CLI — `python -m evaluation.cli --mode <mode>`

`ad_video_analysis/` 디렉토리에서 실행한다. 모든 파이프라인은 하나의 진입점으로 실행한다.

```bash
python -m evaluation.cli --mode <mode> [모드별 옵션]
python -m evaluation.cli --mode <mode> -h   # 모드별 옵션 확인
```

| mode | 역할 | 출력 |
|------|------|------|
| `brief` | scenario_analysis → 브리프 추출 | `brief_analysis.json` |
| `parsed` | scenario/cuts/cut_analysis/scene_analysis/stt/audio 종합 | `parsed_analysis.json` |
| `scenario_eval` | 시나리오 평가 (brief 존재 시 비교 포함) | `evaluation.json` |
| `category` | 카테고리 분석 + `video_category` 컬렉션 적재 | `category_analysis.json` |
| `concept` | `strategy_analysis.json` 을 `ad_concept_reference` 컬렉션에 적재(M3 전략 참고용, `--concept_evaluation` 은 레거시) | `concept_evaluation.json`(레거시, 세그먼트 필터 보조용) |
| `creative` | 크리에이티브 요소 추출 + `ad_production_reference` 컬렉션 적재(M5~M9·스토리보드 연출 참고용) + 세그먼트 클리셰 리포트 | `creative_element_analysis.json` |
| `strategy` | M1·M2·M3 전략 스키마 역추출 | `strategy_analysis.json` |
| `ad_concept_production` | **(권장)** `scenario_analysis` → concept+production 추출 + 두 컬렉션 적재를 한 번에(단일 통합 파이프라인, [ad_concept_production/README.md](ad_concept_production/README.md)) | `concept_analysis.json`, `production_analysis.json` |
| `convert` | parsed/brief → 외부 스키마 일괄 변환 | `<out_dir>/<id>.json` |
| `convert_v2` | parsed → wrapped 스키마 변환 | `<out_dir>/<id>.json` |
| `rename` | 결과 파일을 DB `original_filename` 으로 재명명 복사 | `<out_dir>/<원본명>.json` |

### 예시

```bash
# 브리프 추출 후 시나리오 평가
python -m evaluation.cli --mode brief --video_id 349
python -m evaluation.cli --mode scenario_eval --video_id 349

# Gemini 백엔드로 parsed_analysis 생성
python -m evaluation.cli --mode parsed --video_id 349 --llm_backend gemini

# 카테고리 분석 + 벡터 DB 적재 한 번에
python -m evaluation.cli --mode category --video_id 349 --category_analysis --load_vector \
    --data_dir output/additional_0609/claude

# 전략 역추출 후 ad_concept_reference 적재 (권장 순서 — concept 쪽의 유일한 문서 소스)
python -m evaluation.cli --mode strategy --video_id 349 --data_dir output/product_plan/claude
python -m evaluation.cli --mode concept --video_id 349 --load_vector

# 외부 스키마 변환 (구 --mode 옵션은 --convert_mode 로 변경됨)
python -m evaluation.cli --mode convert --video_dir output/total --out_dir output/converted --convert_mode parsed
```

> 각 하위 모듈은 `python -m evaluation.<폴더>.run` 으로 직접 실행할 수도 있다 (convert 계열은
> `python -m evaluation.convert.convert` 등). 통합 CLI 와 동일한 옵션을 받는다.

### 공통 옵션 (brief/parsed/scenario_eval/category/concept/strategy)

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--video_id` | (필수) | 대상 영상 ID |
| `--data_dir` | 모드별 상이 | `<data_dir>/<video_id>/` 입력 루트 |
| `--llm_backend` | `claude` | `claude` \| `codex` \| `qwen` \| `gemini` (category/strategy 는 qwen 제외) |
| `--codex_model` / `--qwen_model` / `--gemini_model` | — | 백엔드별 모델명 |

> 임베딩 모델: `BAAI/bge-m3` (1024-dim, 한/영 cross-lingual). 변경 시
> `evaluation/category/vector_store.py::EMBEDDING_MODEL` 수정 후 `python db/reembed.py` 로 재적재.
> 벡터 검색 사용법은 [`../db/README.md`](../db/README.md) 참고.

## 참조 벡터 DB 스키마 — 용도별 컬렉션 2개

`generation/v5_m0_m3` 파이프라인이 참고하는 참조 광고 벡터 DB는 용도별로 컬렉션이 나뉜다
(레거시 `video_concept`/`ad_target`/`ad_usp`/`ad_creative` 는 사용하지 않는다 — 아래 참고).
**신규 적재는 `--mode ad_concept_production` 하나로 양쪽 컬렉션을 다 채운다** —
`strategy`→`concept --load_vector`→`creative --extract --load_vector` 3단계 조합은 여전히
동작하지만(모듈별로 프롬프트를 따로 다루고 싶을 때), 일반적인 신규/배치 재구축에는
`ad_concept_production` 을 쓴다.

| 컬렉션 | 소스 | 적재 | 참고 단계 |
|--------|------|------|-----------|
| `ad_concept_reference` | `strategy_analysis.json`(M1 인사이트·M2 포지셔닝·M3 컨셉 역추출 — `--mode strategy` 로 먼저 생성) | `--mode concept --load_vector` ([concept/README.md](concept/README.md)) | M3(컨셉 발산) — 인간 진실·가치 제안에서 출발해 어떤 전략 렌즈로 컨셉을 만들고 why 를 어떻게 증명했는지("왜 이 컨셉인가" 인과) 참고 |
| `ad_production_reference` | `creative_element_analysis.json` | `--mode creative --load_vector` ([creative/README.md](creative/README.md)) | M4~M9·스토리보드 HTML — 연출·촬영 기법·캐스팅 + 설득 엔진·서사 형식·톤 레지스터(M5 반-수렴 참고) |

**영상 전체를 새로 돌릴 때는 세 모드를 모두 실행해야 한다** — `strategy`→`concept --load_vector`
순서를 지키고 `creative --extract --load_vector` 를 빠뜨리면(또는 그 반대) 한쪽 컬렉션이 비어
해당 단계의 검색 도구가 매번 "컬렉션이 비어 있음"만 반환한다.

`ad_concept_reference` 는 애초에 `concept_evaluation.json`(flat 카테고리 라벨만 있고 "왜 이
컨셉인가" 인과가 없음)으로 만들었으나, M3 프롬프트(`generation/v5_m0_m3/prompts/module3.md`)가
실제로 필요로 하는 것은 전략 렌즈·빅아이디어·why 증명 같은 인과 추론이라 `strategy_analysis.json`
로 소스를 교체했다(`concept_evaluation.json` 은 세그먼트 필터 보조로만 선택적 흡수).

레거시 G1~G6 생성 파이프라인(`generation/g1~g6`, `generation/segment_retrieval.py`)이 쓰는
`video_concept`/facet 컬렉션은 이 스키마와 무관하게 남아 있다(`concept_vector_store.py`/
`facet_vector_store.py`, `--load_facets`) — 새 기능을 추가할 때 그 파일들을 재사용하지 않는다.
