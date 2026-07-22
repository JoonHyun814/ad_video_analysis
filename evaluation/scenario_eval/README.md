# evaluation/scenario_eval

시나리오를 평가해 `evaluation.json` 을 생성한다. `brief_analysis.json` 이 있으면
브리프 충실도(brief_fidelity) 비교를 포함하고, 없으면 시나리오 단독 평가로 동작한다.

## 파일 구성

| 파일 | 역할 |
|------|------|
| `run.py` | CLI 실행기 (`python -m evaluation.cli --mode scenario_eval`) |
| `evaluator.py` | 평가 프롬프트 빌드 + 점수 계산 + claude 백엔드 구현 |
| `evaluator_codex.py` / `_gemini.py` / `_qwen.py` | 백엔드별 구현 (프롬프트·점수 계산은 `evaluator.py` 공유) |

평가 JSON 스키마는 `evaluation/schemas.py` 에, 평가 기준은
[`../scenario_checklist.md`](../scenario_checklist.md) 에 정의되어 있다.

## 실행

```bash
python -m evaluation.cli --mode scenario_eval --video_id <ID> [옵션]
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--video_id` | (필수) | 대상 영상 ID |
| `--data_dir` | `output/codex` | `<data_dir>/<video_id>/` 입력·출력 루트 |
| `--llm_backend` | `claude` | `claude` \| `codex` \| `qwen` \| `gemini` |
| `--codex_model` / `--qwen_model` / `--gemini_model` | — | 백엔드별 모델명 |

출력: `<data_dir>/<video_id>/evaluation.json` (전체 점수 + 카테고리별 점수,
`_meta.has_brief` 로 브리프 포함 여부 기록)
