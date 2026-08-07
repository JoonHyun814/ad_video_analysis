# evaluation/strategy

`scenario_analysis.json` 에서 M1(인사이트)·M2(포지셔닝)·M3(컨셉) 전략 스키마를 역추출해
`strategy_analysis.json` (`{"m1": {...}, "m2": {...}, "m3": {...}}`) 으로 저장한다.

이 결과는 [`../../db/README.md`](../../db/README.md)의 `db/chromadb/importers/concept_reference.py`가
`ad_concept_reference` 컬렉션(`generation/v5_m0_m3` M3 컨셉 발산 참고용)의 유일한 문서 소스로
쓴다 — `evaluation/concept/README.md` 참고.

## 파일 구성

| 파일 | 역할 |
|------|------|
| `run.py` | CLI 실행기 (`python -m evaluation.cli --mode strategy`) |
| `strategy_extraction.py` | M1 → M2 → M3 순차 LLM 호출 (뒤 모듈은 앞 모듈 결과를 핸드오프로 받음) |
| `strategy_schemas.py` | `../docs/m1·m2·m3.txt` 영상 생성 프롬프트의 v5 출력 스키마·역할 가이드 정의 |

- `m1`: 소비자 인사이트 — corejob·humantruth·culturalcodes·marketscopes·target·forces·triggers·opportunitytop3·assumptiontop3·verbatim
- `m2`: 포지셔닝 — messagecandidates·positioningstatement·valueproposition·ownedceps·topcompetitor·category·cepcoverage·demandspace·uniqueattributes
- `m3`: 컨셉 — seeds·fixedwhy·concepts (광고에 실제 구현된 컨셉 정확히 1개, 발산 아님)

세 모듈 모두 창작이 아니라 **관찰 기반 역추출**이다: 시나리오에 실제 등장한 장면·카피·연출에
접지해 채우고, 관찰 불가한 추정은 [가설] 태그, 근거 없는 항목은 빈 값으로 남긴다.
앞 모듈이 실패하면 뒤 모듈은 `{"error": "skipped: ..."}` 로 기록된다.

## 실행

```bash
python -m evaluation.cli --mode strategy --video_id <ID> [옵션]
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--video_id` | (필수) | 대상 영상 ID |
| `--data_dir` | `output/codex` | `<data_dir>/<video_id>/scenario_analysis.json` 입력 |
| `--llm_backend` | `claude` | `claude` \| `codex` \| `gemini` |
| `--codex_model` / `--gemini_model` | — | 백엔드별 모델명 |
| `--timeout` | `600` | 모듈별 LLM 호출 타임아웃(초) |

```bash
python -m evaluation.cli --mode strategy --video_id 349 --data_dir output/product_plan/claude
```
