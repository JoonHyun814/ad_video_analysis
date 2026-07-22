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
| `strategy/` | M1·M2·M3 전략 스키마 역추출 | [strategy/README.md](strategy/README.md) |
| `convert/` | 외부 시스템 스키마 변환·재명명 | [convert/README.md](convert/README.md) |

루트 파일:

| 파일 | 역할 |
|------|------|
| `cli.py` | 통합 CLI 진입점 (`--mode` 로 하위 파이프라인 디스패치) |
| `schemas.py` | 브리프/평가 공용 JSON 스키마 정의 |
| `scenario_checklist.md` | 시나리오 평가 체크리스트 |
| `creative_element_schema.md` | 클리셰 분석용 크리에이티브 요소 vectorDB 스키마·enum 사전 (설계 문서) |
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
| `concept` | 컨셉 추출 + `video_concept`/facet 컬렉션 적재 | `concept_evaluation.json` |
| `strategy` | M1·M2·M3 전략 스키마 역추출 | `strategy_analysis.json` |
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

# 컨셉 추출 + video_concept 적재
python -m evaluation.cli --mode concept --video_id 349 --concept_evaluation --load_vector

# 전략 역추출
python -m evaluation.cli --mode strategy --video_id 349 --data_dir output/product_plan/claude

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
