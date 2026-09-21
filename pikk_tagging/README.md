# pikk_tagging 모듈

광고 영상을 **컷 단위로만** pikk(stills.pikk.co.kr) 촬영·연출 기법 어휘 13종으로 태깅하는 파이프라인. 영상 전체 태그는 만들지 않는다.
전처리(컷 감지 → keyframe → frames → OCR → STT → BGM/SFX)는 `pipeline/` 과 **동일한 함수**를 그대로 호출한다.

## 파일 구성

| 파일 | 역할 |
|------|------|
| `vocab.json` | 기법 어휘 13종: 정의·포함/제외 조건·혼동 항목·별칭(tag_synonyms variant)·사이트 비율. 축 3개(camera / lighting_tone / graphics) 정의 |
| `vocab.py` | `vocab.json` 로딩, 별칭 정규화(`normalize_term`), 재현 가능한 셔플(`shuffled`) |
| `preprocess.py` | `pipeline.cli` 전처리 1~7단계 실행(무거운 의존성은 이때만 import) + 캐시 로드 (`run_preprocess`, `load_preprocessed`) |
| `frame_select.py` | 컷당 대표 프레임 균등 샘플링(처음·끝 포함) |
| `prompts.py` | 축별 태깅 프롬프트, 태그별 검증 프롬프트 |
| `llm.py` | 비전 LLM 디스패처 (`gemini` / `openai`, 공용 `utils` 호출기 사용) |
| `schema.py` | LLM 응답 검증: 어휘 밖 id·근거 없는 태그·잘못된 confidence 탈락, 제안(proposals) 별칭 정리 |
| `voting.py` | 축별 N회 결과 다수결 |
| `verify.py` | 후보 태그 1개씩 yes/no 재검증 |
| `tagger.py` | 컷 단위 오케스트레이션 (`tag_video`, `tag_cut`) |
| `cli.py` | 진입점 |
| `evaluate.py` | 골든셋 대비 태그별 precision/recall/F1 |
| `stats.py` | 기법별 태깅률 vs 사이트 비율 진단, 탈락 stage 집계 |
| `results_io.py` | `<root>/<video>/tags.json` 로딩, JSON 저장 (`save_json`) |
| `review.py` | 태깅 결과 리뷰 GUI(단일 HTML) 생성 |
| `review_template.html` | 리뷰 GUI 템플릿 (HTML/CSS/JS, 데이터는 `review.py` 가 주입) |
| `PLAN_RAG_INTEGRATION.md` | 시나리오 에이전트 RAG 통합 계획서 (현황·설계 결정·단계별 게이트) |

## 사전 준비

```
env/db.env    # DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME  (--video_id 사용 시)
env/dir.env   # ROOT_VIDEO_DIR
env/api.env   # GEMINI_API_KEY 또는 OPENAI_API_KEY
```

## CLI 사용법

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
| `--skip_preprocess` | off | out_dir 의 기존 전처리 결과 재사용 (`pipeline` 출력 폴더도 가능) |
| `--preprocess_dir` | 없음 | 기존 전처리 결과 루트(`<root>/<video_id>/`)를 읽고 전처리를 생략. 태깅 결과만 `--out_dir` 에 저장 (`datas/total` 같은 폴더 재사용용) |
| `--cache_dir` | `/root/.cache` | HuggingFace·모델 캐시 루트 |
| `--llm_backend` | `gemini` | `gemini` \| `openai` |
| `--model` | backend 기본값 | 모델명 (`utils` 호출기의 `DEFAULT_MODEL`) |
| `--passes` | `2` | 축별 반복 횟수. 성공한 pass 의 **과반 초과** 득표만 채택 |
| `--max_frames` | `8` | 컷당 LLM 에 넣는 최대 프레임 수 |
| `--no_verify` | off | 태그별 2차 검증 호출 생략 (`verified: null`) |
| `--seed` | `0` | 어휘 순서 셔플 시드 |
| `--max_tags_per_cut` | `5` | 컷당 최대 태그 수 |

```bash
python -m pikk_tagging.cli --video_id 349
python -m pikk_tagging.cli --video_ids 1-10 --passes 3
python -m pikk_tagging.cli --video_id 349 --skip_preprocess --out_dir output   # pipeline 전처리 재사용
python -m pikk_tagging.cli --video_id 1 --preprocess_dir ../datas/total --out_dir ../datas/pikk_data   # 다른 폴더의 전처리 결과 사용
```

전처리는 이 모듈이 만드는 산출물(`cuts/ocr/stt/audio_analysis/tags/proposals.json`, `keyframes/ frames/ stt/`)만 지우고 다시 만든다. 다른 파일은 건드리지 않는다.

## 태깅 흐름 (컷마다)

```
프레임 샘플링(max_frames) ─┬─ camera        ─┐
                           ├─ lighting_tone ─┼─ 축마다 passes 회 생성 (어휘 순서 매번 셔플)
                           └─ graphics(+OCR)─┘        │
                                        schema 검증 → 다수결 → 태그별 검증 → 컷당 상한
```

| 단계 | 하는 일 | 막는 문제 |
|------|---------|-----------|
| 닫힌 어휘 | LLM 은 `vocab.json` 의 id 만 출력. 표기 정규화는 코드(`normalize_term`)가 담당. 어휘 밖 개념은 `proposals` 로만 받음 | 표기 변형 폭증 |
| 근거 우선 | 출력 순서 `observation → tags[{id, frames, evidence, confidence}] → proposals`. 근거 프레임이 범위 밖이거나 근거 문장이 없으면 탈락 | 할루시네이션 |
| 축 분리 · 프레임 샘플링 | 축당 어휘 4~6개만 프롬프트에 넣고, 컷당 최대 `max_frames` 장만 사용 | 긴 컨텍스트 |
| 편향 완화 | 호출마다 어휘 순서 셔플(순서 편향) · 제외 조건/혼동 항목 명시 · 빈 결과 허용 · 축/컷 상한 · 기존 태그·제목 미제공(앵커링) · OCR 은 graphics 축에만 제공 · 인물 식별/외모 평가 금지 | 순서·빈도·앵커링·인물 편향 |
| 검증 | 다수결(자기 일관성) + 태그별 yes/no 재검증(생성 단계 근거는 미제공) | 오탐 |

> JSON 스키마 enum 강제는 `utils/gemini_caller` 가 response schema 를 지원하지 않아 `schema.py` 의 사후 검증(어휘 밖 id 탈락)으로 대신한다.
> `--passes` 중 일부 호출이 실패하면 성공한 pass 수를 분모로 다수결한다 (`votes` 필드에 `득표/성공 pass 수` 기록). 전부 실패하면 `errors` 에 남고 해당 축은 태그가 없다.

## 출력 구조

```
{out_dir}/<video_id>/
├── cuts.json / ocr.json / stt.json / audio_analysis.json   # 전처리 (pipeline 과 동일)
├── keyframes/  frames/  stt/
├── tags.json        # 컷별 태깅 결과
└── proposals.json   # 어휘 밖 제안 검수 큐 (DB·어휘에 자동 반영하지 않음)
```

### tags.json

```json
{
  "video": "349", "vocab_version": "2026-09-21", "backend": "gemini", "model": "models/gemini-2.5-flash-lite",
  "passes": 2, "max_frames": 8, "verify": true, "seed": "0",
  "cuts": [{
    "cut_index": 1, "start_sec": 0.0, "end_sec": 3.9, "frame_times": [0.0, 0.5, "..."],
    "observations": {"camera": "테이블 위 음식을 수직으로 내려다봄", "lighting_tone": "..."},
    "tags": [{
      "id": "탑뷰", "axis": "camera", "confidence": "high", "votes": "2/2",
      "evidence": {"frames": [1, 2], "note": "수직 하향 구도"},
      "verified": true, "verify": {"frames": [2, 3], "reason": "..."}
    }],
    "rejected": [{"id": "로우앵글", "axis": "camera", "stage": "vote", "reason": "votes 1/2"}],
    "proposals": [{"term": "패럴랙스", "axis": "camera", "frames": [3], "evidence": "..."}],
    "errors": []
  }]
}
```

- `rejected.stage`: `schema`(형식·어휘·근거) / `vote` / `verify` / `verify_error`(검증 호출 실패 — 보수적으로 탈락) / `cut_cap`
- 프레임 번호는 `frame_times` 의 1-based 인덱스다.

## 평가 · 진단

```bash
# 골든셋(사람 라벨) 대비 태그별 P/R/F1 — 프롬프트·모델을 바꿀 때마다 회귀 테스트
python -m pikk_tagging.evaluate --golden golden.json --pred_dir outputs/pikk_tagging

# 태깅률 vs 사이트 비율 — 특정 기법 과다 태깅(빈도 편향) 점검, 탈락 stage 집계
python -m pikk_tagging.stats --pred_dir outputs/pikk_tagging
```

골든 형식: `{"<video_id>": {"<cut_index>": ["탑뷰", "로우키"], ...}}` (라벨 없는 컷은 `[]`).

## 리뷰 GUI

keyframe · LLM 에 넣은 프레임 · 태그 · 근거를 한 화면에서 보고 정답/오답을 표시한 뒤 골든셋으로 내보낸다.

```bash
python -m pikk_tagging.review --pred_dir ../datas/pikk_data --preprocess_dir ../datas/total [--priority 7-3,8-2] [--out review.html]
```

생성된 `review.html` 을 브라우저(Chrome/Edge)로 연다. 이미지는 상대경로로 참조하므로 `--out` 과 전처리 폴더의 상대 위치를 옮기면 이미지가 깨진다.

- 카드마다 keyframe, LLM 에 넣은 프레임 썸네일(번호 = 근거의 프레임 번호), 태그 칩(`confidence · 득표 · 검증✓`), 근거·재검증 사유, 탈락 목록, 모델 관찰을 본다. 이미지를 누르면 컷의 전체 프레임을 크게 볼 수 있다(←/→, Esc).
- 칩의 **✗** = 오답, **놓친 기법 추가** 또는 탈락 목록의 **실제로 있음** = 놓친 태그. 칩에 마우스를 올리면 어휘 정의가 보인다.
- **검수 완료**를 체크한 컷만 골든셋에 들어간다. 정답 = (예측 태그 − ✗ 표시) + 놓친 태그. ✗ 를 안 누른 태그는 정답으로 간주한다.
- **골든셋 내보내기** → `golden.json` 다운로드 (`evaluate.py --golden` 입력 형식). 표시 내용은 브라우저 localStorage 에 자동 저장된다(같은 브라우저에서만 유지).
- 필터: 영상 탭 / ★ 추천(`--priority`) / 미검수 / 태그 없음 / 1표 탈락 있음 / 확신 medium / 호출 오류 / 특정 태그.
- 결과를 다시 만들어 `review.html` 을 재생성하면 같은 영상·컷 번호의 기존 표시가 그대로 붙는다. 태깅을 다시 돌렸다면 이전 표시가 새 결과와 맞지 않을 수 있으니 브라우저 저장소를 지우고 시작한다.

## 어휘 갱신

`vocab.json` 은 `stills_pikk` 덤프(수집일 2026-09-15)의 `facet_counts` 기법 필터 13종과 `tag_synonyms`(kind=variant) 별칭, `site_prior`(전체 10,385 장면 대비 기법 필터 건수)로 만들었다.
정의·포함/제외·혼동 항목은 수기 작성이다. 기법을 추가하면 정의를 반드시 함께 쓰고, `evaluate` 로 회귀 확인한다.
