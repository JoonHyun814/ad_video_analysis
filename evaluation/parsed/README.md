# evaluation/parsed

파이프라인 산출물(scenario/cuts/cut_analysis/scene_analysis/stt/audio)을 종합해
`parsed_analysis.json` 을 생성한다.

## 파일 구성

| 파일 | 역할 |
|------|------|
| `run.py` | CLI 실행기 (`python -m evaluation.cli --mode parsed`) |
| `parsed_analysis.py` | 종합 분석 프롬프트 빌드 + claude 백엔드 구현 |
| `parsed_analysis_codex.py` / `_gemini.py` / `_qwen.py` | 백엔드별 구현 (프롬프트는 `parsed_analysis.py` 공유) |

## 입력 파일 (`<data_dir>/<video_id>/`)

| 파일 | 필수 | 설명 |
|------|------|------|
| `scenario_analysis.json` | ○ | 시나리오 분석 결과 |
| `cut_analysis.json` | ○ | 컷 분석 결과 |
| `cuts.json` | ○ | 컷 경계 (`pipeline.cuts.Cut`) |
| `scene_analysis.json` | — | 씬 분석 (없으면 빈 목록) |
| `stt.json` | — | STT 세그먼트 (없으면 빈 목록) |
| `audio_analysis.json` | — | 오디오 분석 (없으면 빈 객체) |

## 실행

```bash
python -m evaluation.cli --mode parsed --video_id <ID> [옵션]
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--video_id` | (필수) | 대상 영상 ID |
| `--data_dir` | `output/codex` | 입력 루트 |
| `--output_dir` | = `--data_dir` | `<output_dir>/<video_id>/parsed_analysis.json` 저장 |
| `--llm_backend` | `claude` | `claude` \| `codex` \| `qwen` \| `gemini` |
| `--codex_model` / `--qwen_model` / `--gemini_model` | — | 백엔드별 모델명 |
