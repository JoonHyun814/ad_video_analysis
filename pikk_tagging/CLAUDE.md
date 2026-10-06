# pikk_tagging 도메인 모듈 개발 가이드

이 문서는 `pikk_tagging/` 하위 도메인 폴더(`angle/`, `focus/`, `lighting/`, `motion/`, `shot_size/`)를 구현하거나 수정할 때 따라야 할 규칙을 정의한다.

---

## 출력 경로 규칙

```
outputs/pikk_output/<domain>/<기법종류>/<영상id>/
```

| 예시 | 경로 |
|------|------|
| 조명 — 픽셀 분류기 | `outputs/pikk_output/lighting/pixel_classifier/<video_id>/lighting_results.json` |
| 모션 — optical_flow | `outputs/pikk_output/motion/optical_flow/<video_id>/motion_results.json` |
| 샷사이즈 — 규칙 기반 | `outputs/pikk_output/shot_size/rule_based/<video_id>/shot_size_results.json` |

- `<domain>`: 폴더명(`angle`, `focus`, `lighting`, `motion`, `shot_size`)
- `<기법종류>`: 같은 도메인 안에서 여러 방법을 비교할 수 있도록 알고리즘/모델명 층 추가 (`pixel_classifier`, `optical_flow`, `ml_model` 등)
- `<영상id>`: youtube_id 또는 영상 파일의 stem(확장자 없는 이름)

`cli.py` 의 `--out_dir` 기본값은 상대경로 `outputs/pikk_output/<domain>/<기법종류>` 로 지정한다.

---

## 도메인 폴더 필수 구성 요소

### 1. 전체 결과 뷰어 (`viewer.py`)

- 분석이 완료된 모든 영상을 한 목록 페이지에서 보여준다.
- 영상 클릭 시 상세 페이지로 이동해 비디오 플레이어 + 분류 결과 타임라인을 표시한다.
- `outputs/pikk_output/<domain>/<기법종류>/` 하위 모든 결과 폴더를 자동 탐색한다.
- Pikk GT 태그(`video_gt_tags.json`)가 있으면 상세 페이지에 함께 표시한다.
- 포트 번호 예약: `lighting=5003`, `motion=5002`, `shot_size=5004`, `focus=5005`, `angle=5006`

### 2. 실험 기록 뷰어 (`exp_server.py`)

- 알고리즘/파라미터 변경 전·후 비교를 위한 before/after 비교 UI.
- 실험 내용은 `docs/experiment_log.html` 에 하드코딩하고 서버가 서빙한다.
- 포트: `viewer.py` 포트 + 3000 이상 오프셋 사용 (예: `lighting exp_server = 8081`).

### 3. 태그 어휘 문서 (`docs/<domain>_tags.md`)

- 이 도메인이 감지 대상으로 삼는 **Pikk 태그** 목록을 정리한 마크다운 문서.
- 분류기 레이블 ↔ Pikk 태그 매핑 표 필수.
- Pikk 태그는 `outputs/pikk_output/pikk_tag_tree.json` 에서 추출한다.
- 현재 분류기가 감지하지 못하는 태그 군도 "미감지" 로 명시한다.

---

## 표준 파일 구조

```
pikk_tagging/<domain>/
├── __init__.py
├── README.md            # 이 도메인 전용 문서 (레이블·파일구성·CLI·출력구조·뷰어)
├── analyzer.py          # 프레임/영상 단위 feature 추출
├── classifier.py        # feature → label 변환 (규칙 or 모델)
├── io.py                # 결과 읽기/쓰기
├── cli.py               # argparse 진입점
├── viewer.py            # 전체 결과 뷰어 (Flask)
├── exp_server.py        # 실험 비교 뷰어 (Flask)
└── docs/
    ├── <domain>_tags.md       # Pikk 태그 어휘 목록
    └── experiment_log.html    # 실험 기록 (exp_server 서빙)
```

---

## README 동기화 의무

도메인 폴더에서 다음 중 하나를 변경하면 같은 커밋에서 `<domain>/README.md` 를 업데이트한다.

- CLI 옵션 추가/제거/기본값 변경
- 분류 레이블 추가/변경
- 파일 추가 또는 함수 시그니처 변경
- 출력 JSON 구조 변경

---

## 공통 패턴 참고

조명 도메인(`lighting/`)이 현재 가장 완성된 구현이다. 새 도메인을 구현할 때 다음을 참고한다.

| 참고 파일 | 내용 |
|-----------|------|
| `lighting/analyzer.py` | 프레임 스텝 순회 + stats dict 반환 패턴 |
| `lighting/classifier.py` | 규칙 분류 + temporal run-length filter |
| `lighting/io.py` | results JSON 저장/로딩 |
| `lighting/viewer.py` | GT 태그 오버레이 + 타임라인 SVG + Flask 라우팅 |
| `lighting/exp_server.py` | before/after API + lazy-load HTML |
