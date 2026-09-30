# pikk_tagging/shot_size

피사체 크기 및 화면 구도로 **샷 사이즈(shot size)**를 분류하는 파이프라인. — **구현 예정**

## 레이블 (계획)

| 레이블 | 한국어 | 설명 |
|--------|--------|------|
| `extreme_close_up` | 익스트림 클로즈업 | 눈·입 등 신체 일부만 화면 가득 |
| `close_up` | 클로즈업 (CU) | 얼굴 또는 물체 클로즈업 |
| `medium_close_up` | 미디엄 클로즈업 (MCU) | 가슴 위·어깨 포함 |
| `medium_shot` | 미디엄 샷 (MS) | 허리 위 전체 |
| `medium_long_shot` | 미디엄 롱 샷 (MLS) | 무릎 위 전체 |
| `long_shot` | 롱 샷 (LS) | 전신 + 배경 일부 |
| `wide_shot` | 와이드 샷 (WS) | 인물 작고 배경 넓음 |
| `extreme_wide_shot` | 익스트림 와이드 샷 (EWS) | 원경·항공·파노라마 |

## 감지 방식 (설계 방향)

- **얼굴/신체 감지**: MediaPipe 또는 OpenCV Haar cascade 로 bounding box 추출
- **피사체 비율**: bbox 면적 / 프레임 면적 → 임계값으로 레이블 결정
- **인물 없는 샷**: 엣지·텍스처 밀도로 클로즈업(제품·음식) vs 와이드 구분

## 파일 구성 (예정)

| 파일 | 역할 |
|------|------|
| `analyzer.py` | 프레임별 피사체 탐지 + bbox 비율 계산 |
| `classifier.py` | bbox 비율 → shot_size 레이블 + temporal smooth |
| `io.py` | shot_size_results.json 읽기/쓰기 |
| `cli.py` | CLI 진입점 |
| `viewer.py` | 전체 결과 뷰어 (포트 5004) |
| `exp_server.py` | 실험 비교 뷰어 |
| [`docs/shot_size_tags.md`](docs/shot_size_tags.md) | Pikk 샷사이즈 관련 태그 어휘 목록 |
| `docs/experiment_log.html` | 실험 기록 |

## 출력 구조 (예정)

```
outputs/pikk_output/shot_size/<기법종류>/<video_id>/
└── shot_size_results.json
```

## 관련 Pikk 태그

샷 사이즈 관련 주요 Pikk 태그 (선별):

| 태그 | 사용수 추정 | 분류기 대응 |
|------|------------|-------------|
| 클로즈업 | 높음 | `close_up` |
| 익스트림클로즈업 | 중간 | `extreme_close_up` |
| 미디엄샷 | 높음 | `medium_shot` |
| 와이드샷 | 높음 | `wide_shot` |
| 롱샷 | 중간 | `long_shot` |
| 버드아이뷰 | 중간 | `extreme_wide_shot` (항공) |

> 상세 태그 어휘 목록은 구현 시 `docs/shot_size_tags.md` 로 분리 작성 예정.
