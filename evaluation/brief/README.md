# evaluation/brief

`scenario_analysis.json` 에서 광고 브리프(`brief_analysis.json`)를 추출한다.

## 파일 구성

| 파일 | 역할 |
|------|------|
| `run.py` | CLI 실행기 (`python -m evaluation.cli --mode brief`) |
| `brief_generator.py` | 브리프 추출 프롬프트 빌드 + claude 백엔드 구현 |
| `brief_generator_codex.py` / `_gemini.py` / `_qwen.py` | 백엔드별 구현 (프롬프트는 `brief_generator.py` 공유) |

브리프 JSON 스키마는 `evaluation/schemas.py::_BRIEF_SCHEMA` 에 정의되어 있다
(generation 모듈의 브리프 생성과 공유).

## 실행

```bash
python -m evaluation.cli --mode brief --video_id <ID> [옵션]
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--video_id` | (필수) | 대상 영상 ID |
| `--data_dir` | `output/codex` | `<data_dir>/<video_id>/scenario_analysis.json` 입력 |
| `--output_dir` | = `--data_dir` | `<output_dir>/<video_id>/brief_analysis.json` 저장 |
| `--llm_backend` | `claude` | `claude` \| `codex` \| `qwen` \| `gemini` |
| `--codex_model` / `--qwen_model` / `--gemini_model` | — | 백엔드별 모델명 |
