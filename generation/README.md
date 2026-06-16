# generation 모듈

신규 광고 브리프·시나리오를 생성한다. 단일 단계 (`--brief`, `--scenario`) 또는 M1~M7 전체 파이프라인.

## 파일 구성

| 파일 | 역할 |
|------|------|
| `cli.py` | 진입점 (모드: `--brief` / `--scenario` / `--pipeline` / `--stage`) |
| `brief_generator.py` | 웹 검색 기반 브리프 생성 |
| `web_searcher.py` | 검색 결과 수집 |
| `scenario_generator{,_codex,_gemini,_qwen}.py` | 단일 단계 시나리오 생성 (레거시) |
| `scenario_pipeline.py` | M1~M7 오케스트레이터 |
| `m1_consumer_insight.py` | M1 — 소비자 인사이트 |
| `m2_positioning.py` | M2 — 포지셔닝 전략 |
| `m3_concept_divergence.py` | M3 — 컨셉 발산 (5~8개) |
| `m4_concept_kill.py` | M4 — 컨셉 비평·킬 (GATE A) |
| `m5_dr_script.py` | M5 — DR 스크립트 |
| `m6_red_team.py` | M6 — 레드팀 프리모템 |
| `m7_validation.py` | M7 — 합성 사전스크린 + 인간 게이트 |

## M1~M7 단계

| 모듈 | 내용 |
|------|------|
| M1 | 소비자 인사이트 추출 |
| M2 | 포지셔닝 전략 |
| M3 | 컨셉 발산 (5~8개) |
| M4 | 컨셉 비평·킬 (GATE A) |
| M5 | DR 스크립트 생성 |
| M6 | 레드팀 프리모템 |
| M7 | 합성 사전스크린 + 인간 게이트 |

## 사용법

```bash
python -m generation.cli --brand <브랜드> --product <제품> [모드] [옵션]
```

| 모드 | 동작 |
|------|------|
| `--brief` | 웹 검색 기반 브리프 생성 → `<brand>_<product>.json` |
| `--scenario` | 단일 단계 시나리오 생성 (레거시) |
| `--pipeline` | M1→M7 전체 자동 실행 |
| `--stage m1\|m2\|...\|m7` | 특정 단계만 실행 (이전 단계 출력 필요) |

| 입력 옵션 (미입력 시 모델이 채움) | 설명 |
|------|------|
| `--usp`, `--target_age`, `--target_persona`, `--positioning`, `--slogan` | 텍스트 |
| `--ingredients`, `--functions` | 다중 값 (`--ingredients a b c`) |

| 공통 | 기본값 | 설명 |
|------|--------|------|
| `--llm_backend` | `claude` | `claude` \| `codex` \| `qwen` \| `gemini` |
| `--codex_model` / `--qwen_model` / `--gemini_model` | — | 백엔드별 모델명 |
| `--output_dir` | `output/generation` | 결과 저장 |

## 예시

```bash
# 풀 파이프라인 (M1~M7)
python -m generation.cli --brand 설화수 --product 윤조에센스 --pipeline --llm_backend gemini

# 단일 단계 재실행 (M3 만, 이전 M1·M2 출력 필요)
python -m generation.cli --brand 설화수 --product 윤조에센스 --stage m3

# 웹 검색 브리프만 생성
python -m generation.cli --brand 설화수 --product 윤조에센스 --brief
```

## 출력 파일명

`<output_dir>/<brand>_<product>.json` — 브리프
`<output_dir>/<brand>_<product>_<stage>.json` — M1~M7 각 단계
