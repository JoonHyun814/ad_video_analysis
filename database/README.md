# database 모듈

`v5runs`/`v5storyboards`/`v5videos` (shortform-pipeline 생성 결과 DB) 조회, 자산(프롬프트·
이미지·영상) 추출, 그리고 완성된 영상을 재분석한 `scenario_analysis` 를 원본과 비교하는
스크립트 모음. `pipeline/` 모듈이 쓰는 `ad-video-analysis` 라벨링 DB와는 다른 DB다.

## 파일 구성

| 파일 | 역할 |
|------|------|
| `scripts/db_config.py` | `database/.env` 를 읽어 pymysql 연결을 여는 공용 헬퍼 |
| `scripts/list_recent_runs.py` | `v5runs` 최근 목록 조회 CLI (`--limit`/`--since`/`--until`/`--status`/`--save`) |
| `scripts/export_run_assets.py` | runid별 스토리보드 이미지·프롬프트·영상을 `exports/<runid>/` 로 다운로드하는 CLI |
| `scripts/matching.py` | prompt·스토리보드 이미지·영상이 모두 있는 (run, video, storyboard) 매칭 단위 조회 |
| `scripts/fetch_assets.py` | 매칭 단위 하나의 원본(prompt/이미지/영상)을 로컬로 다운로드 |
| `scripts/compare_scenario.py` | `scenario_analysis` 와 원본(prompt+스토리보드+이미지)을 claude -p 로 비교 |
| `scripts/run_comparison_pipeline.py` | 위 셋을 엮어 매칭 데이터 일괄 처리하는 CLI 진입점 |

## 사전 준비

`database/.env` 에 DB 접속 정보 필요 (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`).
`claude` CLI 가 PATH 에 있어야 한다 (`scenario_analysis` 생성·비교 단계에서 `claude -p` 호출).

## `run_comparison_pipeline.py` — scenario 생성·원본 비교 일괄 파이프라인

`prompt`(v5videos.prompt) + 스토리보드 이미지(v5storyboards.machinejson.m9.scenes[].sketchurl)
+ 영상(v5videos.videourl) 이 모두 있는 (run, video) 조합을 최근 순으로 골라, 각 영상을
`pipeline.cli` 로 재분석해 `scenario_analysis` 를 만들고, 그 결과를 원본과 비교한다.

```bash
python scripts/run_comparison_pipeline.py --limit 20 --out_dir ../output
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--limit` | `20` | 처리할 매칭 건수. `v5runs` 개수가 아니라 **prompt+이미지+영상이 모두 있는** (run, video) 조합 개수 기준 |
| `--out_dir` | (필수) | 결과 저장 루트. 하위에 `<run_id>/video<id>/` 생성 |
| `--llm_backend` | `claude` | `scenario_analysis` 생성 LLM 백엔드 (`pipeline.cli` 그대로 전달: `claude`\|`codex`\|`qwen`\|`gemini`) |
| `--max_cuts` | `50` | `scenario_analysis` 생성 시 최대 컷 수 상한. `pipeline.cli` 기본값(10)보다 커야 컷수 비교(`cut_count`)가 병합으로 왜곡되지 않는다 |
| `--overwrite_assets` | off | 이미 내려받은 자산도 다시 다운로드 |

### 매칭 단위(unit) 정의

`v5videos` 1건은 `storyboardid` 로 특정 `v5storyboards` 1건(=하나의 컨셉)에서 나온 프롬프트로
생성된다. 한 run 에 스토리보드(컨셉)가 여러 개거나 영상이 여러 번 생성됐을 수 있으므로,
run 단위가 아니라 **(run_id, video_id, storyboard_id)** 조합 단위로 비교한다 — 스토리보드
이미지가 `machinejson` 파싱 결과 하나도 없는 건은 비교가 불가능하므로 애초에 제외된다.

### 처리 단계 (유닛 1건당)

```
[1/3] 자산 다운로드      prompt.txt / 스토리보드 이미지 / 영상  → <run_id>/video<id>/assets/
[2/3] scenario_analysis   pipeline.cli --video_path <영상>       → <run_id>/video<id>/scenario/
[3/3] 원본 비교           claude -p (--add-dir 이미지)            → <run_id>/video<id>/comparison.json
```

`comparison.json` 이 이미 있으면 해당 유닛은 스킵한다 — 배치 중간에 중단돼도 재실행 시 이어서
처리된다. 각 유닛 처리 직후 `<out_dir>/summary.json` 을 갱신한다(전체 결과 배열, 실패 건은
`error` 필드 포함).

### 출력 구조

```
{out_dir}/
├── summary.json                        # 전체 유닛 결과 배열 (실패 시 error 필드)
└── <run_id>/
    └── video<video_id>/
        ├── assets/
        │   ├── prompts/video<id>_prompt.txt
        │   ├── images/scene<no>.png     # 스토리보드 씬 이미지
        │   └── videos/video<id>.mp4
        ├── scenario/
        │   └── video<id>/               # pipeline.cli 출력 (cuts.json, scenario_analysis.json 등)
        └── comparison.json              # 비교 결과
```

### `comparison.json` 비교 요인

`factors` 하위 9개 요인 각각 `{match, expected, actual, evidence}` 형식. `cut_count` 만
코드로 직접 계산(스토리보드 씬의 `shots` 합계 vs `scenario_analysis.scenes` 개수)하고,
나머지는 claude -p 가 원본 프롬프트·스토리보드 씬 묘사·이미지·`scenario_analysis` 를 함께
보고 판정한다.

| 요인 | 설명 |
|------|------|
| `cut_count` | 컷 수 일치 (코드 계산) |
| `cut_order` | 컷/씬 순서가 내용상 대응하는지 |
| `character_count` | 등장 인물 수 |
| `character_appearance` | 인물 외형 묘사 일치 |
| `scene_description` | 장면(배경·구도) 묘사 일치 |
| `dialogue` | 대사·나레이션 내용 일치 |
| `text_overlay` | 화면 텍스트 일치 |
| `scene_duration` | 씬별 길이 비율 유사도 |
| `brand_logo_exposure` | 브랜드/로고 노출 유무·타이밍 일치 |

`overall_match_rate` = `match: true` 요인 수 / 전체 요인 수(9).

```json
{
  "run_id": "v5s5a256db73b76",
  "video_id": 1750,
  "storyboard_id": 3815,
  "concept_index": 1,
  "factors": {
    "cut_count": {"match": true, "expected": 10, "actual": 10, "evidence": "..."},
    "cut_order": {"match": true, "expected": "...", "actual": "...", "evidence": "..."}
  },
  "overall_match_rate": 0.89,
  "summary": "전체 비교 총평"
}
```
