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
| `scripts/precheck.py` | scenario 생성 전 저비용 사전 검증 — 영상 프레임 vs 스토리보드 이미지로 오매칭 여부 판정 |
| `scripts/run_comparison_pipeline.py` | 위를 엮어 매칭 데이터 일괄 처리하는 CLI 진입점 |
| `scripts/prompt_context.py` | `compare_scenario.py`/`advanced_metrics.py` 공용 스토리보드 프롬프트 포맷터 |
| `scripts/advanced_metrics_prompts.py` | T2VScore-A/VBench-2.0 심화 지표 프롬프트·JSON 스키마 상수 |
| `scripts/advanced_metrics_scoring.py` | claude -p 원시 응답에서 정답률·순차매칭 점수를 코드로 계산 |
| `scripts/advanced_metrics.py` | T2VScore-A/VBench-2.0 심화 지표를 claude -p 로 산출(`compute_advanced_metrics`) |
| `scripts/run_advanced_metrics.py` | 기존 `comparison.json` 에 `advanced_metrics` 를 병합 저장하는 CLI 진입점 |
| `scripts/build_manifest.py` | 비교 결과 디렉토리를 스캔해 GUI 뷰어용 `manifest.json` 생성 + 뷰어 템플릿 복사 |
| `viewer/index.html` | prompt·스토리보드 이미지·영상·비교 결과를 한 화면에서 보는 정적 GUI (뷰어 템플릿, git 추적) |

## 사전 준비

`database/.env` 에 DB 접속 정보 필요 (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`).
`claude` CLI 가 PATH 에 있어야 한다 (`scenario_analysis` 생성·비교 단계에서 `claude -p` 호출).

## `run_comparison_pipeline.py` — scenario 생성·원본 비교 일괄 파이프라인

`prompt`(v5videos.prompt) + 스토리보드 이미지(v5storyboards.machinejson.m9.scenes[].sketchurl)
+ 영상(v5videos.videourl) 이 모두 있는 (run, video) 조합을 최근 순으로 골라, 각 영상을
`pipeline.cli` 로 재분석해 `scenario_analysis` 를 만들고, 그 결과를 원본과 비교한다.

```bash
python scripts/run_comparison_pipeline.py --limit 20 --out_dir ../output

# 후반 합성 전 원본 영상 기준으로도 비교 (postprocessed 결과와 별도 저장)
python scripts/run_comparison_pipeline.py --limit 5 --out_dir ../output --video_source original
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--limit` | `20` | 처리할 매칭 건수. `v5runs` 개수가 아니라 **prompt+이미지+영상이 모두 있는** (run, video) 조합 개수 기준 |
| `--out_dir` | (필수) | 결과 저장 루트. 하위에 `<run_id>/video<id>/` 생성 |
| `--video_source` | `postprocessed` | 비교에 쓸 영상. `postprocessed`: 나레이션/캡션 후반 합성 완료본만(QA 테스트 제외). `original`: 후반 합성 여부와 무관하게 AI 원본 생성 영상(`videourl`)을 그대로 사용 — 같은 videoid 라도 `video<id>_original/` 에 따로 저장돼 `postprocessed` 결과와 섞이지 않고, 요약도 `summary_original.json` 으로 분리된다 |
| `--llm_backend` | `claude` | `scenario_analysis` 생성 LLM 백엔드 (`pipeline.cli` 그대로 전달: `claude`\|`codex`\|`qwen`\|`gemini`) |
| `--max_cuts` | `50` | `scenario_analysis` 생성 시 최대 컷 수 상한. `pipeline.cli` 기본값(10)보다 커야 컷수 비교(`cut_count`)가 병합으로 왜곡되지 않는다 |
| `--overwrite_assets` | off | 이미 내려받은 자산도 다시 다운로드 |
| `--skip_precheck` | off | 오매칭 사전 검증(아래 참고)을 생략하고 바로 scenario 생성으로 진행 |
| `--require_verified_caption` | off | (`--video_source postprocessed` 전용) caption 소스 중 해시 포함 파일명(`_crf23_fast_none_`)만 후보로 선택 — "QA 테스트 요청 제외" 절 참고 |

### 매칭 단위(unit) 정의

`v5videos` 1건은 `storyboardid` 로 특정 `v5storyboards` 1건(=하나의 컨셉)에서 나온 프롬프트로
생성된다. 한 run 에 스토리보드(컨셉)가 여러 개거나 영상이 여러 번 생성됐을 수 있으므로,
run 단위가 아니라 **(run_id, video_id, storyboard_id)** 조합 단위로 비교한다 — 스토리보드
이미지가 `machinejson` 파싱 결과 하나도 없는 건은 비교가 불가능하므로 애초에 제외된다.

### 영상 소스 선택 — `video_source`

**나레이션 음성 또는 로고/QR/오버레이 후반 합성이 끝난 영상이 없는 건은 비교 대상에서 아예
제외한다.** AI가 막 생성한 원본(`v5videos.videourl`)만 있고 후반 합성본이 없는 건은
`fetch_matched_units()` 의 SQL WHERE 절에서 걸러져 `--limit` 개수에도 안 잡힌다
(`matching.py::_resolve_video`). 우선순위:

1. `caption` — `v5videos.captionvideourl`(+`captionrenderstatus='done'`): 로고·QR·키워드·
   오버레이 문구 burn-in, 나레이션이 있었다면 그 오디오까지 포함해 재인코딩된 최종본
2. `narration` — `v5videos.narrationvideourl`(+`narrationstatus='done'`): TTS 나레이션만
   합성된 버전 (caption 이 없을 때만)

어떤 소스를 썼는지는 `comparison.json.video_source` 에 기록되고, `claude -p` 비교 프롬프트에도
"이 영상은 후반 합성이 끝난 최종본" 이라는 안내가 추가돼 — 사람이 나중에 얹은 로고·오버레이
문구를 스토리보드에 없다는 이유만으로 결함 처리하지 않도록 한다.

### QA 테스트 요청 제외

실측 결과, `captionvideourl` 이 있는 videoid 상당수가 실제 클라이언트 납품이 아니라 PTBWA
내부 QA 테스트였다("QA v0.9 오버레이 문구", "424", "ㅇㅇ" 같은 placeholder 문구, 담당자도
`@ptbwa.com` 내부 계정). `v5postwork.overlaymsg`/`keywordtext` 가 다음 패턴에 해당하는
videoid 는 매칭에서 제외한다(`matching.py::_looks_like_qa_test`):

- `QA v0.9` 같은 명시적 QA 버전 라벨
- 순수 숫자 placeholder (`"424"`, `"2222"`)
- 자모만 있는 의미없는 문구 (`"ㅇㅇ"`)

이 필터는 **명백한 테스트 요청만** 걸러낸다 — `"집에서도 매장 그대로, DBH100"` 처럼 문구
자체는 정상인데 렌더 워커가 엉뚱한 원본 영상을 합성한 경우는 텍스트 패턴으로 못 잡는다.
이런 케이스는 아래 사전 검증이 잡는다.

**파일명 패턴 실측**: `captionvideourl` 파일명을 까보면 `<runid>_<videoid>.mp4`(원본과
동일한 단순 이름)와 `<runid>_<videoid>_crf23_fast_none_<해시>.mp4`(잡별 고유 해시 포함)
두 가지가 섞여 있는데, 오매칭은 **전자(해시 없는 쪽)에서만** 확인됐다(표본 6건 중 3건 오매칭
vs 후자 7건 중 0건). 렌더 워커에 코드 경로가 두 개 있고, 해시 없는 쪽이 동일 videoid 반복
재처리 시 파일명이 겹쳐 덮어쓰기/경쟁 상태를 일으키는 것으로 추정된다.
`--require_verified_caption` 로 해시 포함 caption만 고를 수 있다 — precheck 로도 다 걸러지지
않는(비결정적) 오매칭 위험을 미리 줄이고 싶을 때 쓴다.

### 사전 검증(precheck) — 오매칭 감지

`scenario_analysis` 생성(`pipeline.cli`, 10~30분)을 돌리기 전에 영상 프레임 3장(초·중·후반)과
스토리보드 이미지 최대 3장(처음·중간·마지막 씬)을 `claude -p` 비전 1회로 비교해 "같은 광고
캠페인인지"만 저비용으로 판정한다(`precheck.py`). 프레임 1장 vs 이미지 1장만 비교하면 같은
광고 안의 다른 순간(착장 장면 vs 제품 클로즈업)을 다른 광고로 오판하므로 반드시 여러 장을
같이 준다.

- `same_ad: false` 로 판정되면 무거운 파이프라인을 건너뛰고 `<run_id>/video<id>/skipped.json`
  에 사유를 남긴다 (`overall_match_rate` 자체가 없음 — 애초에 비교 대상이 아니었다는 뜻).
- LLM 응답 파싱 실패 등 판정 불가 상황은 **fail-open**(진행)한다 — 이 체크는 명백한 오매칭만
  저비용으로 거르는 용도지, 애매한 경우까지 차단하려는 게 아니다.
- `--skip_precheck` 로 끌 수 있다.

### 처리 단계 (유닛 1건당)

```
[1/4] 자산 다운로드      prompt.txt / 스토리보드 이미지 / 영상  → <run_id>/video<id>/assets/
[2/4] 사전 검증          영상 프레임 vs 스토리보드 이미지 (claude -p) — 오매칭이면 여기서 중단
[3/4] scenario_analysis   pipeline.cli --video_path <영상>       → <run_id>/video<id>/scenario/
[4/4] 원본 비교           claude -p (--add-dir 이미지)            → <run_id>/video<id>/comparison.json
```

`comparison.json` 또는 `skipped.json` 이 이미 있으면 해당 유닛은 스킵한다 — 배치 중간에
중단돼도 재실행 시 이어서
처리된다. 각 유닛 처리 직후 `<out_dir>/summary.json` 을 갱신한다(전체 결과 배열, 실패 건은
`error` 필드, 사전 검증에서 걸러진 건은 `skipped: true` 필드 포함).

### 출력 구조

```
{out_dir}/
├── summary.json                        # 전체 유닛 결과 배열 (실패 시 error, 오매칭 시 skipped 필드)
└── <run_id>/
    └── video<video_id>/
        ├── assets/
        │   ├── prompts/video<id>_prompt.txt
        │   ├── images/scene<no>.png     # 스토리보드 씬 이미지 (+사전 검증용 _video_frame_N.jpg)
        │   └── videos/video<id>.mp4
        ├── scenario/                    # 사전 검증 통과 시에만 생성됨
        │   └── video<id>/               # pipeline.cli 출력 (cuts.json, scenario_analysis.json 등)
        ├── skipped.json                 # 오매칭으로 판정된 경우 (scenario/, comparison.json 없음)
        └── comparison.json              # 비교 결과 (사전 검증 통과 시에만)
```

**원본/후반합성 분리 컨벤션**: `run_comparison_pipeline.py` 자체는 `--video_source`(`original`/
`postprocessed`) 에 따라 `--out_dir` 를 자동으로 나누지 않는다 — 두 모드 결과를 뷰어에서 뚜렷이
구분해 보려면 실행 시 `--out_dir` 자체를 `<out_dir>/original`, `<out_dir>/postprocessed` 로 각각
지정한다. 아래 GUI 뷰어가 `<out_dir>/original/*/video*/`(원본)와
`<out_dir>/postprocessed/*/video*/`(후반합성) 양쪽을 스캔해 하나의 뷰어에 합치되 `stage` 필드로
구분한다. (`--video_source original` 은 `video<id>_original/` 처럼 비디오 폴더명에도 `_original`
접미사를 붙이므로, 같은 run_id 에 두 소스가 섞여도 폴더명만으로도 구분 가능하다.)

```bash
python scripts/run_comparison_pipeline.py --limit 10 --out_dir ../output/postprocessed --require_verified_caption
python scripts/run_comparison_pipeline.py --limit 10 --out_dir ../output/original --video_source original
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
  "video_source": "caption",
  "factors": {
    "cut_count": {"match": true, "expected": 10, "actual": 10, "evidence": "..."},
    "cut_order": {"match": true, "expected": "...", "actual": "...", "evidence": "..."}
  },
  "overall_match_rate": 0.89,
  "summary": "전체 비교 총평"
}
```

## `run_advanced_metrics.py` — T2VScore-A / VBench-2.0 심화 지표 추가

`comparison.json` 의 9개 factor 판정과 별개로, T2V 생성 품질 평가 논문 두 편의 방법론을
옮겨와 **기존 결과에 추가**하는 스크립트다. `run_comparison_pipeline.py` 를 다시 돌릴 필요
없이 이미 받아둔 `assets/`(스토리보드 이미지)와 `scenario/`(재분석 결과)를 그대로 재사용해서,
`comparison.json` 에 `advanced_metrics` 키를 병합 저장한다.

```bash
python scripts/run_advanced_metrics.py --out_dir ../output/postprocessed
python scripts/run_advanced_metrics.py --out_dir ../output/original --video_source original
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--out_dir` | (필수) | `run_comparison_pipeline.py` 에 쓴 것과 동일한 경로 (`comparison.json` 을 재귀 스캔) |
| `--video_source` | `postprocessed` | 해당 `comparison.json` 을 만들 때 쓴 `--video_source` 와 동일해야 스토리보드를 DB 에서 다시 찾을 수 있다 |
| `--overwrite` | off | 이미 `advanced_metrics` 가 있어도 다시 계산 |
| `--timeout` | `600` | claude -p 타임아웃(초) |

### T2VScore-A — 요소 분해 정합성 (Wu et al. 2024, arXiv:2401.07781 §3.1)

스토리보드 전체에서 검증 가능한 핵심 요소(주체·속성·동작) 6~10개를 뽑아 각각이
`scenario_analysis` 에서 확인되는지 개별 판정하고, `score = 검증된 요소 수 / 전체 요소 수`
로 집계한다. 기존 `character_appearance`/`scene_description` 같은 요인 단위 통짜 판정보다
더 잘게 쪼갠 원자적 체크라 — 어떤 세부 요소가 구체적으로 빠졌는지 요소별로 드러난다.

```json
"t2vscore_a": {
  "elements": [
    {"element": "...", "type": "entity|attribute|action|global", "source_scene": 1, "verified": false, "evidence": "..."}
  ],
  "verified_count": 2, "total_count": 9, "score": 0.222
}
```

### VBench-2.0 서브셋 — 7개 차원 (Zheng et al. 2025, arXiv:2503.21755 §III-A)

VBench-2.0 18개 차원 중, 별도 전문가 모델(GRiT·UMT·자체 학습 이상탐지기 등) 없이 claude -p
만으로 논문 방법론 그대로 재현 가능한 7개만 구현했다. 나머지(Human Anatomy·Instance
Preservation·Diversity 등)는 자체 학습 체크포인트나 동일 프롬프트 다중 샘플링이 필요해
이 프로젝트 구조상 재현하지 않는다.

각 차원은 스토리보드가 해당 능력을 애초에 요구하는지(`applicable`) 먼저 판단하고, 요구하지
않으면 `score: null` 로 집계에서 제외한다.

| 차원 | 논문 근거 | 적용 조건 | 점수 방식 |
|------|-----------|-----------|-----------|
| `complex_plot` | §III-A(3-e) | 다단계 서사(사건 전개)가 있는 스토리보드 | 순차 매칭 — 앞에서부터 맞은 비트 수 / 전체(첫 불일치 지점 이후는 계산에서 제외) |
| `complex_landscape` | §III-A(3-f) | 여러 장소/배경 전환이 있는 스토리보드 | `complex_plot` 과 동일한 순차 매칭 |
| `human_interaction` | §III-A(3-d) | 인물 2인 이상의 물리적 상호작용이 명시된 경우 | 이진 판정(1.0/0.0) |
| `motion_order_understanding` | §III-A(3-c) | 한 샷 안에 순서가 명시된 동작이 2개 이상인 경우 | 두 동작 모두 순서대로 확인돼야 1.0(논문 원칙) |
| `dynamic_attribute` | §III-A(3-a) | 시간에 따른 속성 변화(색상·형태 등)가 명시된 경우 | redundant 3질문(초기/최종/변화 여부) 정답률 |
| `dynamic_spatial_relationship` | §III-A(3-b) | 물체/인물의 위치 이동이 명시된 경우 | `dynamic_attribute` 와 동일한 3질문 정답률 |
| `motion_rationality` | §III-A(5-a) | "동작이 실제 결과를 남겨야/남기면 안 된다"는 지시가 있는 경우(예: 먹기·마시기·자르기) | redundant 3질문 정답률 — 허위 동작·허위 정지를 잡아낸다 |

```json
"vbench2": {
  "complex_plot": {"applicable": true, "elements": [{"beat": "...", "matched": false}], "matched_count": 0, "total_count": 6, "score": 0.0, "evidence": "..."},
  "human_interaction": {"applicable": false, "score": null, "evidence": "해당 없는 이유"}
},
"vbench2_summary": {"applicable_dimensions": 5, "total_dimensions": 7, "avg_score": 0.533}
```

`expected`/`actual` 을 예/아니오 질문쌍으로 받는 3개 차원(`dynamic_attribute`/
`dynamic_spatial_relationship`/`motion_rationality`)과, 순차 매칭 2개 차원(`complex_plot`/
`complex_landscape`) 은 정답 여부·집계 점수를 LLM 이 아니라 `advanced_metrics_scoring.py`
가 코드로 계산한다 — `compare_scenario.py` 의 `cut_count` 처리와 같은 원칙(셀 수 있는 값을
LLM 산술에 맡기면 신뢰도가 떨어진다)이다.

## GUI 뷰어 — `build_manifest.py` + `viewer/index.html`

`run_comparison_pipeline.py` 결과(prompt/이미지/영상/비교)를 한 화면에서 보기 위한 정적 뷰어.
`<out_dir>/*/video*/`(원본)와 `<out_dir>/postprocessed/*/video*/`(후반합성) 양쪽을 스캔해
합치고, 유닛마다 `stage`("original"|"postprocessed") 를 매겨 좌측 상단 탭(전체/원본/후반합성)
으로 구분해서 볼 수 있다. 탭으로 거른 뒤 유닛을 검색·정렬해 고르면 우측에 프롬프트·스토리보드
이미지·완성 영상·요인별 비교표가 표시된다. `run_advanced_metrics.py` 로 `advanced_metrics`
가 채워진 유닛은 요인별 비교표 아래에 T2VScore-A/VBench-2.0 카드가 추가로 표시된다(없는
유닛은 이 카드 자체가 나타나지 않는다) — `build_manifest.py` 는 `comparison.json` 을 그대로
담으므로 별도 코드 변경 없이 자동 반영된다.

```bash
python scripts/build_manifest.py --out_dir ../../output   # manifest.json 생성 + 뷰어 복사
cd ../../output && python -m http.server 8000              # 정적 서버 실행
# 브라우저에서 http://localhost:8000 접속
```

`index.html` 을 `file://` 로 직접 열면 `manifest.json`/이미지/영상 fetch 가 브라우저
보안 정책에 막히므로 반드시 http 서버로 띄운다. `run_comparison_pipeline.py` 를 재실행해
유닛이 늘어나면 `build_manifest.py` 를 다시 돌려 `manifest.json` 을 갱신한다(뷰어 자체는
`database/viewer/index.html` 원본을 그대로 복사하므로 `--out_dir` 안의 사본을 직접 고치지
않는다 — 뷰어 수정은 원본에서 한다).
