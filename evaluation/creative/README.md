# evaluation/creative

클리셰 분석 파이프라인 — [`creative_element_schema.md`](creative_element_schema.md) 설계 문서의 구현 (v2).

`scenario_analysis.json` 에서 크리에이티브 요소(오프닝 훅, 인물 연출, 감각 시연, 신뢰 장치,
제품 컷, 색·조명, 카피 장치, 서사, 사운드, CTA)를 enum 으로 추출해 벡터 DB 에 적재하고,
세그먼트(예: beauty×스킨케어×15초) 내 빈도 집계로 클리셰/클리셰 파괴 요소를 판정한다.

핵심 원칙 두 가지:

- **클리셰 여부는 적재 시점에 판정하지 않는다** — DB 에는 중립적 요소만 저장하고,
  판정은 리포트 시점에 세그먼트 상대 빈도로 계산한다 (코퍼스가 바뀌면 판정도 바뀐다).
- **(v2) element_type 10종은 전 산업 공통, subtype 은 공용 사전 + 산업 팩 병합** —
  추출 시 `category_analysis.json` 의 industry_category 로 팩(beauty/tech_electronics/entertainment)을
  선택한다. 산업 관통 클리셰는 type/공용 subtype 레벨에서 교차 비교된다.
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
| `subtypes_packs.py` | 산업별 subtype 확장 팩 (beauty / tech_electronics / entertainment) |
| `element_analysis.py` | LLM 추출 (claude) — 시나리오+산업 팩 → `creative_element_analysis.json` |
| `element_vector_store.py` | 컬렉션 2개 upsert/조회 + v1 파일 legacy 정규화 |
| `cliche_aggregate.py` | 세그먼트 빈도 집계 + 판정 (strong_cliche/convention/minor/cliche_breaker) |

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
| `--data_dir` | `output/total` | `<data_dir>/<video_id>/scenario_analysis.json` 입력 (industry 는 같은 폴더의 `category_analysis.json` 에서 판별) |
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

## 향후 확장 (설계 문서 참고)

- `other`/`description` 임베딩 K-Means 군집화로 enum 에 없는 신규 클리셰 발견
- `creative_dedup_key` 기반 동일 소재 지면 변형 자동 중복 제거
