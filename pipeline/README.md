# pipeline 모듈

광고 영상을 12단계로 분석해 재제작 가능한 시나리오를 생성하는 파이프라인.

## 파일 구성

| 파일 | 역할 |
|------|------|
| `video_loader.py` | DB에서 video_id로 영상 경로 조회 |
| `cuts.py` | 컷 경계 감지 및 컷 병합 유틸리티 |
| `transnetv2_cuts.py` | TransNetV2 딥러닝 기반 컷 경계 감지 |
| `keyframe.py` | 각 컷의 중간 프레임을 JPG로 추출 |
| `frames.py` | 영상 전체에서 지정 fps로 프레임 추출 |
| `ocr.py` | EasyOCR로 이미지에서 텍스트 추출 |
| `stt.py` | Whisper + 화자 분리(NeMo MSDD)로 STT 수행 |
| `audio_analysis.py` | BGM 음악 이론 분석(키·템포·라우드니스) + SFX 이벤트 감지 |
| `audio_clap.py` | LAION CLAP 모델로 BGM 장르·무드 태깅 및 SFX 자연어 분류 |
| `face_detection.py` | OpenCV Haar Cascade로 프레임별 얼굴 감지 및 NMS |
| `scene_analysis.py` | keyframe을 claude -p로 분석해 장면 묘사 생성 |
| `scene_analysis_codex.py` | keyframe을 codex exec로 분석 |
| `cut_analysis.py` | 컷 내 fps=2 프레임 시퀀스를 claude -p로 시간 흐름 묘사 |
| `cut_analysis_codex.py` | 컷 내 프레임 시퀀스를 codex exec로 분석 |
| `cast_analysis.py` | 얼굴 크롭 + cut_analysis로 등장 인물 cast 리스트 생성 (claude -p) |
| `cast_analysis_codex.py` | 얼굴 크롭 + cut_analysis로 cast 리스트 생성 (codex exec) |
| `scenario_analysis.py` | cut_analysis·OCR·STT·cast를 종합해 시나리오 JSON 생성 (claude -p) |
| `scenario_analysis_codex.py` | 동일 데이터를 codex exec로 시나리오 생성 |
| `cli.py` | 파이프라인 전체를 실행하는 CLI 진입점 |

## 사전 준비

```
env/db.env   # DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
env/dir.env  # ROOT_VIDEO_DIR
```

## CLI 사용법

`ad_video_analysis/` 디렉토리에서 실행한다.

```bash
python -m pipeline.cli --video_id <ID> [옵션]
```

### 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--video_id` | (필수) | `video_uploads.id` 값 |
| `--cut_backend` | `transnetv2` | 컷 감지 백엔드 (`transnetv2` \| `scenedetect`) |
| `--threshold` | `0.3` / `27.0` | 컷 감지 민감도 (백엔드별 기본값) |
| `--max_cuts` | 없음 | 최대 컷 수. 초과 시 짧은 컷을 이웃에 병합 |
| `--out_dir` | `output/<video_id>` | 결과 저장 디렉토리 |
| `--llm_backend` | `claude` | LLM 백엔드 (`claude` \| `codex`). scene·cut·cast·scenario 전체 적용 |
| `--skip_scene_analysis` | off | scene_analysis 단계 생략. 기존 scene_analysis.json 유지 |
| `--skip_cut_analysis` | off | cut_analysis 단계 생략. 기존 cut_analysis.json 유지 |

### 예시

```bash
# 기본 실행 (TransNetV2, claude 백엔드)
python -m pipeline.cli --video_id 1

# Codex 백엔드로 LLM 분석 전체 실행
python -m pipeline.cli --video_id 1 --llm_backend codex

# 결과 디렉토리 지정
python -m pipeline.cli --video_id 1 --out_dir tmp/results/1

# 최대 5컷으로 제한
python -m pipeline.cli --video_id 1 --max_cuts 5

# cut_analysis 재사용, scene_analysis 생략
python -m pipeline.cli --video_id 1 --skip_scene_analysis --skip_cut_analysis
```

## 파이프라인 단계

```
[1/12]  영상 정보 조회     DB에서 video_id → 영상 절대경로
[2/12]  컷 감지            TransNetV2 (또는 scenedetect) → cuts.json
[3/12]  Keyframe 추출      각 컷 중간 프레임 → keyframes/
[4/12]  Frames 추출        영상 전체 fps=2 추출 → frames/
[5/12]  OCR                frames/ 전체 기준 EasyOCR → ocr.json
[6/12]  STT + 화자 분리    Whisper + NeMo MSDD → stt.json
[7/12]  BGM + SFX 분석     librosa + CLAP → audio_analysis.json
[8/12]  Face detection      Haar Cascade + NMS → face_detection.json
[9/12]  Scene 분석          keyframe 1장/컷 → scene_analysis.json  (--llm_backend)
[10/12] Cut 분석            컷 내 프레임 시퀀스 흐름 묘사 → cut_analysis.json  (--llm_backend)
[11/12] Cast 분석           얼굴 크롭 + cut_analysis → cast_analysis.json  (--llm_backend)
[12/12] 시나리오 분석       전체 데이터 종합 → scenario_analysis.json  (--llm_backend)
```

## 출력 구조

```
{out_dir}/
├── cuts.json               # 컷 목록 (index, start/end frame·sec)
├── ocr.json                # 프레임별 OCR 텍스트
├── stt.json                # STT 세그먼트 (start_sec, text, speaker)
├── audio_analysis.json     # BGM 음악 분석 + SFX 이벤트
├── face_detection.json     # 프레임별 얼굴 bbox·area_ratio
├── scene_analysis.json     # 컷별 keyframe 장면 묘사
├── cut_analysis.json       # 컷별 시간 흐름 묘사 (flow, subjects, camera 등)
├── cast_analysis.json      # 등장 인물 목록 [{id, description}]
├── scenario_analysis.json  # 완성 시나리오 (title, brand, cast, scenes, ...)
├── keyframes/              # 컷별 중간 프레임 (1장/컷)
│   ├── cut_001_frame_00016.jpg
│   └── ...
├── frames/                 # fps=2 전체 프레임
│   ├── frame_000000.jpg
│   └── ...
└── face_crops/             # cast_analysis용 컷별 얼굴 크롭
    ├── face_cut01.jpg
    └── ...
```

## 주요 JSON 형식

### cuts.json

```json
[
  {"index": 1, "start_frame": 0, "end_frame": 32, "start_sec": 0.0, "end_sec": 1.068},
  {"index": 2, "start_frame": 33, "end_frame": 64, "start_sec": 1.101, "end_sec": 2.135}
]
```

### audio_analysis.json

```json
{
  "bgm": {
    "overall": {"key": "C", "scale": "major", "tempo_bpm": 120.0, "loudness_lufs": -14.2},
    "cuts": [{"cut_index": 1, "genre_tags": ["pop", "electronic"], "mood_tags": ["energetic"]}]
  },
  "sfx": {"summary": "박수 소리 2회, 효과음 1회", "events": [...]}
}
```

### cast_analysis.json

```json
[
  {"id": "캐릭터1", "description": "30대 남성. 짧은 검은 머리, 감성적인 인상. 주인공 역할."},
  {"id": "캐릭터2", "description": "20대 여성. 밝은 미소, 조수석 탑승자."}
]
```

### scenario_analysis.json

```json
{
  "title": "광고 제목",
  "brand": "브랜드명",
  "concept": "핵심 컨셉 한 줄",
  "narrative": "전체 서사 흐름",
  "cast": [{"id": "캐릭터1", "description": "..."}],
  "scenes": [
    {
      "cut_index": 1,
      "time": "0.00~3.90s",
      "beats": [
        {"type": "background", "description": "배경 묘사"},
        {"type": "camera", "description": "클로즈업, 정적"},
        {"type": "action", "cast": "캐릭터1", "description": "기타를 안고 고개를 든다"},
        {"type": "music", "description": "잔잔한 어쿠스틱 기타"},
        {"type": "dialogue", "cast": "캐릭터1", "description": "어린왕자 Your Melody"}
      ]
    }
  ],
  "key_messages": ["핵심 메시지"],
  "production_notes": "재제작 시 참고 사항"
}
```

## 컷 감지 백엔드

### TransNetV2 (기본)

딥러닝 기반 장면 전환 감지. 정확도가 높으나 초기 모델 로딩에 수 초 소요.

- `threshold`: 0.0~1.0, 낮을수록 민감 (기본 0.3)
- TensorFlow + ffmpeg 필요

### scenedetect

PySceneDetect ContentDetector. 프레임 간 HSV 히스토그램 차이 기반.

- `threshold`: 낮을수록 민감 (기본 27.0)
- 경량, 빠름

## --max_cuts 병합 알고리즘

`max_cuts` 지정 시 컷 수가 목표에 도달할 때까지 반복 병합한다.

1. 현재 컷 목록에서 가장 짧은 컷(프레임 수 기준)을 찾는다.
2. 앞뒤 이웃 중 더 짧은 쪽에 흡수시킨다 (동률이면 앞쪽).
3. 컷 수가 `max_cuts` 이하가 될 때까지 반복.
