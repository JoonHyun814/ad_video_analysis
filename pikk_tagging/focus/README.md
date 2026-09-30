# pikk_tagging/focus

포커스 패턴(얕은 피사계 심도·랙 포커스·딥 포커스 등)을 분류하는 파이프라인. — **구현 예정**

## 레이블 (계획)

| 레이블 | 설명 |
|--------|------|
| `shallow_dof` | 얕은 피사계 심도 — 피사체는 선명, 배경은 흐림 (보케) |
| `deep_focus` | 딥 포커스 — 전경부터 배경까지 전체 선명 |
| `rack_focus` | 랙 포커스 — 컷 내부에서 초점 이동 (전경→배경 또는 반대) |
| `out_of_focus` | 전체 아웃 포커스 — 피사체도 배경도 모두 흐림 (의도적 블러) |
| `normal` | 표준 — 위 조건 미해당 |

## 감지 방식 (설계 방향)

- **Laplacian variance**: 화면 영역별 선명도 점수; 중앙 vs 외곽 비교 → `shallow_dof`
- **Temporal sharpness delta**: 연속 프레임 간 선명도 급변 → `rack_focus`
- **전체 블러 임계값**: 전체 Laplacian variance 낮음 → `out_of_focus`
- **균일 선명도**: 전체 영역 선명도 고르게 높음 → `deep_focus`

## 파일 구성 (예정)

| 파일 | 역할 |
|------|------|
| `analyzer.py` | 프레임별 영역 선명도(Laplacian variance) 계산 |
| `classifier.py` | 선명도 패턴 → focus 레이블 + temporal smooth |
| `io.py` | focus_results.json 읽기/쓰기 |
| `cli.py` | CLI 진입점 |
| `viewer.py` | 전체 결과 뷰어 (포트 5005) |
| `exp_server.py` | 실험 비교 뷰어 |
| [`docs/focus_tags.md`](docs/focus_tags.md) | Pikk 포커스 관련 태그 어휘 목록 |
| `docs/experiment_log.html` | 실험 기록 |

## 출력 구조 (예정)

```
outputs/pikk_output/focus/<기법종류>/<video_id>/
└── focus_results.json
```

## 관련 Pikk 태그

포커스 관련 주요 Pikk 태그 (선별):

| 태그 | 분류기 대응 |
|------|------------|
| 얕은피사계심도 / 아웃포커싱 / 보케 | `shallow_dof` |
| 랙포커스 / 포커스이동 | `rack_focus` |
| 딥포커스 | `deep_focus` |
| 소프트포커스 / 몽환적블러 | `out_of_focus` |

> 상세 태그 어휘 목록은 구현 시 `docs/focus_tags.md` 로 분리 작성 예정.
