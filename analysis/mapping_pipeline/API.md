# 컷-씬 매핑 API 문서

베이스 URL: `http://localhost:8000`

---

## 서버 실행

```bash
cd ad_video_analysis
python -m mapping_pipeline.api          # 기본 포트 8000
python -m mapping_pipeline.api 9000     # 포트 지정
```

Swagger UI: `http://localhost:8000/docs`

---

## 엔드포인트

### GET /health

서버 상태를 확인한다.

**응답 200**

```json
{ "status": "ok" }
```

---

### POST /analyze

영상 파일과 시나리오를 받아 컷 분석 및 씬 매핑 결과를 반환한다.

**Content-Type**: `multipart/form-data`

#### 요청 필드

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| `video_file` | file | ✅ | — | 분석할 영상 파일 (mp4) |
| `scenario_file` | file | ※ | — | 시나리오 `.txt` 파일 |
| `scenario_text` | string | ※ | `""` | 시나리오 텍스트 직접 입력 |
| `max_cuts` | integer | | `10` | 최대 컷 수 |
| `threshold` | float | | `27.0` | scenedetect 컷 감지 민감도 (낮을수록 민감) |
| `gemini_model` | string | | `models/gemini-2.5-flash-lite` | 사용할 Gemini 모델명 |

※ `scenario_file`과 `scenario_text` 중 하나는 반드시 제공해야 한다. 둘 다 있으면 `scenario_file`이 우선된다.

#### 응답 200

```json
{
  "cut_analysis": [
    {
      "cut_index": 1,
      "start_sec": 0.0,
      "end_sec": 3.54,
      "n_frames": 7,
      "flow": "제품이 테이블 위에 놓이며 클로즈업 → 손이 집어 듦",
      "subjects": "음료 캔, 손",
      "cast": "없음",
      "camera": "static",
      "text_flow": "없음",
      "mood_shift": "없음"
    }
  ],
  "cut_scene_mapping": [
    {
      "scene": 1,
      "label": "제품 등장",
      "cut_indices": [1, 2],
      "start_s": 0.0,
      "end_s": 6.12
    }
  ],
  "tokens": {
    "input": 12430,
    "output": 860,
    "thinking": 0
  },
  "pipeline_time_s": 47.3,
  "out_dir": "output/ad_sample_1749123456"
}
```

중간 결과 파일은 `out_dir` 경로에 저장된다.

| 파일 | 내용 |
|------|------|
| `cuts.json` | scenedetect 감지 컷 목록 |
| `cut_analysis.json` | Gemini Vision 컷 분석 결과 |
| `cut_scene_mapping.json` | 씬 매핑 결과 + 토큰·시간 |
| `keyframes/` | 각 컷 중간 프레임 이미지 |
| `frames/` | fps=2 전체 프레임 이미지 |

#### 응답 422 — 시나리오 누락

```json
{
  "detail": "scenario_file 또는 scenario_text 중 하나를 반드시 제공해야 합니다."
}
```

#### 응답 500 — 파이프라인 오류

```json
{
  "detail": "<오류 메시지>"
}
```

---

## cut_analysis 필드 설명

| 필드 | 설명 |
|------|------|
| `cut_index` | 컷 번호 (1부터) |
| `start_sec` / `end_sec` | 컷 시작·종료 시각 (초) |
| `n_frames` | 분석에 사용된 프레임 수 |
| `flow` | 컷 내 동작·변화 흐름 (시작→중간→끝) |
| `subjects` | 등장 인물·사물 |
| `cast` | 인물별 외모·표정·역할 (없으면 `"없음"`) |
| `camera` | 카메라 무브먼트 (static / pan / zoom / tilt / tracking 등) |
| `text_flow` | 텍스트 등장·변화·소멸 흐름 (없으면 `"없음"`) |
| `mood_shift` | 분위기 변화 (없으면 `"없음"`) |

## cut_scene_mapping 필드 설명

| 필드 | 설명 |
|------|------|
| `scene` | 씬 번호 |
| `label` | 씬 레이블 (시나리오 기반) |
| `cut_indices` | 해당 씬에 속하는 컷 번호 목록 |
| `start_s` / `end_s` | 씬 시작·종료 시각 (초) |
