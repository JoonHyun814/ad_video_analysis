# analysis/

영상 분석 관련 파이프라인 모음. 각 서브모듈 작업 전 해당 CLAUDE.md 만 읽어라.

| 서브모듈 | 역할 | CLAUDE.md |
|----------|------|-----------|
| `pikk_tagging/` | Pikk 기법 컷별 태깅 (어휘·프롬프트·검증) | [../pikk_tagging/CLAUDE.md](../pikk_tagging/CLAUDE.md) |
| `evaluation/` | 평가·카테고리·벡터 적재 | [../evaluation/CLAUDE.md](../evaluation/CLAUDE.md) |
| `pipeline/` | 영상 분석 단계 실행 | [../pipeline/CLAUDE.md](../pipeline/CLAUDE.md) |
| `mapping_pipeline/` | 외부 영상 매핑 (CLI/API/Gradio) | [../mapping_pipeline/CLAUDE.md](../mapping_pipeline/CLAUDE.md) |
| `Decoding_the_Hook_pipeline/` | 훅 3초 기법 추출·BERTopic | [../Decoding_the_Hook_pipeline/CLAUDE.md](../Decoding_the_Hook_pipeline/CLAUDE.md) |

> 리팩토링 완료 후 각 서브모듈은 이 폴더 아래로 이동한다.
> 현재 코드는 프로젝트 루트 직하에 있다.
