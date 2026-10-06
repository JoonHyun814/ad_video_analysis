# pikk_tagging 모듈

광고 영상을 **컷 단위로만** pikk(stills.pikk.co.kr) 촬영·연출 기법 어휘 13종으로 태깅하는 파이프라인. 영상 전체 태그는 만들지 않는다.  
전처리(컷 감지 → keyframe → frames → OCR → STT → BGM/SFX)는 `pipeline/` 과 **동일한 함수**를 그대로 호출한다.

개발 가이드 및 도메인 폴더 규칙 → [`CLAUDE.md`](CLAUDE.md)

---

## 도메인 서브모듈

| 폴더 | 분류 대상 | 상태 |
|------|-----------|------|
| [`motion/`](motion/README.md) | 카메라 모션 (pan·zoom·rotate·static) | ✅ 구현 완료 |
| [`lighting/`](lighting/README.md) | 조명 유형 (high_key·low_key·backlight·normal) | ✅ 구현 완료 |
| [`shot_size/`](shot_size/README.md) | 샷 사이즈 (CU·MS·WS 등) | 예정 |
| [`focus/`](focus/README.md) | 포커스 패턴 (shallow_dof·rack_focus 등) | 예정 |
| [`angle/`](angle/README.md) | 카메라 앵글 (eye_level·high·low·dutch 등) | 예정 |
| [`LLM/`](LLM/README.md) | Vision LLM (Qwen2.5-VL) 기반 다중 도메인 분류 | ✅ 구현 완료 |

---

## Vision LLM 파이프라인 (`LLM/`)

Qwen2.5-VL 로컬 모델로 fps=2 프레임별 태그를 생성하고 도메인별 대표 태그를 추출한다.  
motion 도메인은 다중 프레임 컨텍스트가 필요하므로 제외.

```bash
python -m pikk_tagging.LLM.cli --video path/to/video.mp4 --target_domain angle,focus
python -m pikk_tagging.LLM.viewer  # http://localhost:5007
```

자세한 옵션 → [`LLM/README.md`](LLM/README.md)

---

## LLM 기반 종합 태거 (tagger.py / cli.py)

컷별로 LLM 비전 모델을 사용해 pikk 기법 어휘 13종을 태깅하는 메인 파이프라인.

### 파일 구성

| 파일 | 역할 |
|------|------|
| `vocab.json` | 기법 어휘 13종: 정의·포함/제외 조건·혼동 항목·별칭·사이트 비율. 축 3개(camera / lighting_tone / graphics) 정의 |
| `vocab.py` | `vocab.json` 로딩, 별칭 정규화(`normalize_term`), 재현 가능한 셔플(`shuffled`) |
| `preprocess.py` | `pipeline.cli` 전처리 1~7단계 실행 + 캐시 로드 (`run_preprocess`, `load_preprocessed`) |
| `frame_select.py` | 컷당 대표 프레임 균등 샘플링(처음·끝 포함) |
| `prompts.py` | 축별 태깅 프롬프트, 태그별 검증 프롬프트 |
| `llm.py` | 비전 LLM 디스패처 (`gemini` / `openai`, 공용 `utils` 호출기 사용) |
| `schema.py` | LLM 응답 검증: 어휘 밖 id·근거 없는 태그·잘못된 confidence 탈락, proposals 별칭 정리 |
| `voting.py` | 축별 N회 결과 다수결 |
| `verify.py` | 후보 태그 1개씩 yes/no 재검증 |
| `tagger.py` | 컷 단위 오케스트레이션 (`tag_video`, `tag_cut`) |
| `cli.py` | 진입점 |
| `evaluate.py` | 골든셋 대비 태그별 precision/recall/F1 |
| `stats.py` | 기법별 태깅률 vs 사이트 비율 진단, 탈락 stage 집계 |
| `results_io.py` | `<root>/<video>/tags.json` 로딩, JSON 저장 (`save_json`) |
| `review.py` | 태깅 결과 리뷰 GUI(단일 HTML) 생성 |
| `review_template.html` | 리뷰 GUI 템플릿 (HTML/CSS/JS, 데이터는 `review.py` 가 주입) |
| `extract_videos.py` | SQL 덤프(stills_pikk) → `pikk_video_catalog.csv/.json` 추출 |
| `download_videos.py` | `pikk_video_catalog.csv` → YouTube 영상 일괄 다운로드 (yt-dlp, 병렬) |
| `extract_tag_tree.py` | SQL 덤프 → `pikk_tag_tree.json` 태그 트리 추출 |
| `PLAN_RAG_INTEGRATION.md` | 시나리오 에이전트 RAG 통합 계획서 |

### 사전 준비

```
env/db.env    # DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME  (--video_id 사용 시)
env/dir.env   # ROOT_VIDEO_DIR
env/api.env   # GEMINI_API_KEY 또는 OPENAI_API_KEY
```

### CLI 사용법

`ad_video_analysis/` 디렉토리에서 실행한다.

```bash
python -m pikk_tagging.cli --video_id <ID> [옵션]
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--video_id` / `--video_ids` / `--video_path` | (택1 필수) | `pipeline.cli` 와 동일. `--video_ids` 는 `1-5,7` 형식 |
| `--cut_backend` | `transnetv2` | 컷 감지 (`transnetv2` \| `scenedetect`) |
| `--threshold` | 백엔드별 | 컷 감지 민감도 |
| `--max_cuts` | `10` | 최대 컷 수 (초과 시 짧은 컷 병합) |
| `--out_dir` | `outputs/pikk_tagging` | 결과 루트. `<video_id>` 하위 폴더가 추가됨 |
| `--skip_preprocess` | off | out_dir 의 기존 전처리 결과 재사용 |
| `--preprocess_dir` | 없음 | 기존 전처리 결과 루트 재사용 (`<root>/<video_id>/`) |
| `--cache_dir` | `/root/.cache` | HuggingFace·모델 캐시 루트 |
| `--llm_backend` | `gemini` | `gemini` \| `openai` |
| `--model` | backend 기본값 | 모델명 (`utils` 호출기의 `DEFAULT_MODEL`) |
| `--passes` | `2` | 축별 반복 횟수 |
| `--max_frames` | `8` | 컷당 LLM 에 넣는 최대 프레임 수 |
| `--no_verify` | off | 태그별 2차 검증 호출 생략 |
| `--seed` | `0` | 어휘 순서 셔플 시드 |
| `--max_tags_per_cut` | `5` | 컷당 최대 태그 수 |

```bash
python -m pikk_tagging.cli --video_id 349
python -m pikk_tagging.cli --video_ids 1-10 --passes 3
python -m pikk_tagging.cli --video_id 349 --skip_preprocess --out_dir output
python -m pikk_tagging.cli --video_id 1 --preprocess_dir ../datas/total --out_dir ../datas/pikk_data
```

### 태깅 흐름 (컷마다)

```
프레임 샘플링(max_frames) ─┬─ camera        ─┐
                           ├─ lighting_tone ─┼─ 축마다 passes 회 생성 (어휘 순서 매번 셔플)
                           └─ graphics(+OCR)─┘        │
                                        schema 검증 → 다수결 → 태그별 검증 → 컷당 상한
```

| 단계 | 하는 일 | 막는 문제 |
|------|---------|-----------|
| 닫힌 어휘 | LLM 은 `vocab.json` 의 id 만 출력. 어휘 밖 개념은 `proposals` 로만 받음 | 표기 변형 폭증 |
| 근거 우선 | 근거 프레임이 범위 밖이거나 근거 문장이 없으면 탈락 | 할루시네이션 |
| 축 분리 | 축당 어휘 4~6개만 프롬프트에 넣음 | 긴 컨텍스트 |
| 편향 완화 | 어휘 순서 셔플·빈 결과 허용·인물 식별 금지 | 순서·빈도·앵커링 편향 |
| 검증 | 다수결(자기 일관성) + 태그별 yes/no 재검증 | 오탐 |

### 출력 구조

```
{out_dir}/<video_id>/
├── cuts.json / ocr.json / stt.json / audio_analysis.json
├── keyframes/  frames/  stt/
├── tags.json
└── proposals.json
```

`tags.json` 의 `rejected.stage`: `schema` / `vote` / `verify` / `verify_error` / `cut_cap`.

---

## 데이터 준비 유틸리티

```bash
# SQL 덤프 → 영상 카탈로그
python -m pikk_tagging.extract_videos --sql path/to/stills_pikk.sql --out-dir output/pikk_output

# YouTube 영상 다운로드
python -m pikk_tagging.download_videos \
    --catalog output/pikk_output/pikk_video_catalog.csv \
    --out-dir output/pikk_output \
    --cookies path/to/cookies.txt
```

다운로드 상세 옵션(쿠키·병렬·JS 런타임 등): `download_videos.py` 헤더 주석 참고.

---

## 평가 · 진단

```bash
python -m pikk_tagging.evaluate --golden golden.json --pred_dir outputs/pikk_tagging
python -m pikk_tagging.stats --pred_dir outputs/pikk_tagging
```

골든 형식: `{"<video_id>": {"<cut_index>": ["탑뷰", "로우키"], ...}}`

## 리뷰 GUI

```bash
python -m pikk_tagging.review --pred_dir ../datas/pikk_data --preprocess_dir ../datas/total [--priority 7-3,8-2] [--out review.html]
```

생성된 `review.html` 을 브라우저로 열고, 칩의 **✗** = 오답, **놓친 기법 추가** = 누락 태그 표시, **골든셋 내보내기** → `golden.json`.

## 어휘 갱신

`vocab.json` 은 `stills_pikk` 덤프(수집일 2026-09-15)의 `facet_counts` 기법 필터 13종과 `tag_synonyms`(kind=variant) 별칭으로 만들었다. 기법을 추가하면 정의와 함께 `evaluate` 로 회귀 확인한다.
