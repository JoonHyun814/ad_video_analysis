# CLAUDE.md

## 폴더 구조

작업 전 해당 폴더의 CLAUDE.md 를 먼저 읽어라. 세부 규칙은 하위 CLAUDE.md 에 있다.

| 폴더 | 역할 | CLAUDE.md |
|------|------|-----------|
| `analysis/` | 영상 분석 파이프라인 전체 | [analysis/CLAUDE.md](analysis/CLAUDE.md) |
| `generation/` | 브리프·시나리오 생성 (M1~M7) | [generation/CLAUDE.md](generation/CLAUDE.md) |
| `train/` | 학습 데이터셋·트레이너 | [train/CLAUDE.md](train/CLAUDE.md) |
| `database/` | 영상 ID DB · 벡터 DB · Pikk DB | [database/CLAUDE.md](database/CLAUDE.md) |
| `utils/` | 공통 헬퍼 (LLM 호출·JSON 파싱·env 로딩) | [utils/CLAUDE.md](utils/CLAUDE.md) |
| `env/` | 환경 변수 파일 | [env/CLAUDE.md](env/CLAUDE.md) |

> 리팩토링 진행 중. 기존 코드 일부는 루트 직하(`pikk_tagging/`, `evaluation/`, `pipeline/` 등)에 있을 수 있다.

---

## Python 코딩 규칙

- **파일 1개 = 책임 1개** · 최대 200줄 · 함수 최대 30줄
- 타입 힌트 필수 · f-string 사용 · 공개 함수에 한 줄 docstring
- **경로·DB·자격증명 하드코딩 금지** — 반드시 `env/` 파일에서 읽는다
- LLM 호출·JSON 파싱은 새로 구현 전 `utils/CLAUDE.md` 확인

---

## README 동기화 의무

CLI 옵션·함수 시그니처·파일·출력 구조·환경 변수가 바뀌면 같은 커밋에서 해당 모듈 README 도 업데이트한다.
