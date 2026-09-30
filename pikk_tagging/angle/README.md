# pikk_tagging/angle

카메라 앵글(eye level·high angle·low angle·dutch·bird's eye)을 분류하는 파이프라인. — **구현 예정**

## 레이블 (계획)

| 레이블 | 설명 |
|--------|------|
| `eye_level` | 아이 레벨 — 피사체와 수평, 표준 시점 |
| `high_angle` | 하이 앵글 — 위에서 내려다봄 (내려다보기) |
| `low_angle` | 로우 앵글 — 아래에서 올려다봄 (올려보기) |
| `bird_eye` | 버드 아이 / 탑뷰 — 완전 수직 하향 시점 |
| `dutch_angle` | 더치 앵글 — 카메라 기울어진 사선 구도 (긴장·혼란 표현) |
| `worm_eye` | 웜 아이 — 극단적 하향에서 올려다봄 |

## 감지 방식 (설계 방향)

- **수평선(Horizon line) 검출**: Hough 선 변환으로 수평선 위치 추정 → 중앙 기준 편차로 high/low 구분
- **소실점(Vanishing point)**: 원근 수렴점 위치 → `bird_eye` (화면 중앙 수직), `worm_eye` (하단 수렴)
- **Roll angle**: 수평선 기울기 → `dutch_angle` (15° 이상)
- **신체/얼굴 위치**: 인물 bounding box 상단·하단 비율 보조 지표

## 파일 구성 (예정)

| 파일 | 역할 |
|------|------|
| `analyzer.py` | 프레임별 수평선·소실점·roll angle 추출 |
| `classifier.py` | 기하 특징 → angle 레이블 + temporal smooth |
| `io.py` | angle_results.json 읽기/쓰기 |
| `cli.py` | CLI 진입점 |
| `viewer.py` | 전체 결과 뷰어 (포트 5006) |
| `exp_server.py` | 실험 비교 뷰어 |
| [`docs/angle_tags.md`](docs/angle_tags.md) | Pikk 앵글 관련 태그 어휘 목록 |
| `docs/experiment_log.html` | 실험 기록 |

## 출력 구조 (예정)

```
outputs/pikk_output/angle/<기법종류>/<video_id>/
└── angle_results.json
```

## 관련 Pikk 태그

앵글 관련 주요 Pikk 태그 (선별):

| 태그 | 분류기 대응 |
|------|------------|
| 탑뷰 / 버드아이뷰 / 오버헤드 | `bird_eye` |
| 로우앵글 / 앙각 | `low_angle` |
| 하이앵글 / 부감 | `high_angle` |
| 아이레벨 | `eye_level` |
| 더치앵글 | `dutch_angle` |
| 웜아이뷰 | `worm_eye` |

> 상세 태그 어휘 목록은 구현 시 `docs/angle_tags.md` 로 분리 작성 예정.
