# evaluation/convert

분석 결과 JSON 을 외부 시스템 스키마로 변환·재명명한다.

## 파일 구성

| 파일 | mode | 역할 |
|------|------|------|
| `convert.py` | `convert` | `parsed_analysis.json` → `claude_preprocessed_v1` 스키마 / `brief_analysis.json` 그대로 저장 |
| `convert_v2.py` | `convert_v2` | `parsed_analysis.json` 을 `parsed` 키로 감싼 wrapped 스키마 (VideoLabelingTool 호환 메타 부여) |
| `rename_to_original.py` | `rename` | `<id>.json` 파일들을 DB `video_uploads.original_filename` 기준으로 복사·재명명 |

## `convert` — 외부 스키마 변환

```bash
python -m evaluation.cli --mode convert --video_dir <루트> --out_dir <저장경로> [--convert_mode parsed|brief]
```

`<video_dir>/<id>/` 안의 분석 결과를 모아 `<out_dir>/<id>.json` 으로 저장한다.

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--video_dir` | (필수) | `<video_id>` 하위 폴더들이 있는 루트 |
| `--out_dir` | (필수) | 결과 저장 디렉토리 |
| `--convert_mode` | `parsed` | `parsed`: parsed_analysis → claude_preprocessed_v1 / `brief`: brief_analysis 그대로 |

> 구버전 CLI 의 `--mode parsed|brief` 옵션은 통합 CLI 의 `--mode` 와 충돌해 `--convert_mode` 로 변경됐다.

## `convert_v2` — wrapped 스키마 변환

```bash
python -m evaluation.cli --mode convert_v2 --video_dir <루트> --out_dir <저장경로>
```

`parsed_analysis.json` 을 가공 없이 `parsed` 키로 감싸고, 상위에 VideoLabelingTool 호환
메타(`video_id`, `original_filename`, `model_cuts`, `parse_success`, `human_label`, `match` 등)를
부여한다. `model_cuts` 은 `parsed.cuts` 의 `cut_id/start_sec/end_sec` 에서 추린다.

## `rename` — DB original_filename 재명명

```bash
python -m evaluation.cli --mode rename --video_dir <입력> --out_dir <저장경로>
```

`<video_dir>/<id>.json` 파일들을 DB `video_uploads.original_filename` 기준으로 복사·재명명한다.
확장자는 `.json` 으로 교체, Windows 금지문자(`<>:"/\\|?*`)는 `_` 로 살균, DB 는 IN 쿼리 1회로
일괄 조회, 이름 충돌 시 `__<video_id>` 접미사 자동 부여.
