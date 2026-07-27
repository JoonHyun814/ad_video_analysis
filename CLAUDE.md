# CLAUDE.md

## 작업 절차 — README 우선

이 저장소는 모듈별 README 가 1차 문서다. 어떤 모듈을 손대기 전에 해당 폴더의 README 부터 읽고, 변경 후에는 README 도 같이 갱신한다.

### 작업 시작 전 — 해당 모듈 README 읽기

| 작업 대상 | 참조할 문서 |
|-----------|-------------|
| 전체 구조·환경 설정 | [`README.md`](README.md) |
| `pipeline/` 영상 분석 단계 추가·수정 | [`pipeline/README.md`](pipeline/README.md) |
| `evaluation/` 평가·카테고리·벡터 적재 | [`evaluation/README.md`](evaluation/README.md) |
| `train_pipeline/` 학습 데이터셋·트레이너 | [`train_pipeline/README.md`](train_pipeline/README.md) |
| `mapping_pipeline/` 외부 영상 매핑 (CLI/API/Gradio) | [`mapping_pipeline/README.md`](mapping_pipeline/README.md) |
| `generation/` 브리프·시나리오 생성 (M1~M7) | [`generation/README.md`](generation/README.md) |
| `db/` MySQL·ChromaDB | [`db/README.md`](db/README.md) |
| `utils/` LLM 호출·JSON 파싱·env 로딩 | [`utils/README.md`](utils/README.md) |

LLM 호출이나 JSON 파싱이 필요하면 새로 구현하지 말고 먼저 `utils/README.md` 의 헬퍼 목록을 확인한다.

### 변경 후 — README 동기화 의무

다음 중 하나라도 해당하면 같은 PR/커밋에서 README 를 업데이트한다.

- **CLI 인자 추가/제거/기본값 변경** → 해당 모듈 README 의 옵션 표 갱신
- **공개 함수·클래스 추가/시그니처 변경** → 모듈 README 의 파일 구성 표 또는 함수 표 갱신
- **새 파일/스크립트 추가** → 모듈 README 의 파일 구성 표에 행 추가
- **출력 파일·디렉토리 구조 변경** → 모듈 README 의 출력 구조 갱신
- **환경 변수·env 파일 추가** → 본 CLAUDE.md 의 환경 변수 표 + `env/README.md` 갱신
- **새 Python 패키지 설치** → 루트 `CLAUDE.md` 의 패키지 표, `Dockerfile`, `setup_venv.ps1` 동기화

README 가 코드와 어긋난 채로 커밋하지 않는다. 의도적으로 미반영하는 경우(예: WIP) 만 PR 설명에 명시한다.

---

## Python 코딩 컨벤션

### 모듈화 원칙
- **파일 1개 = 책임 1개.** 연결, 쿼리, 출력, CLI 진입점은 각각 분리한다.
- **파일 최대 200줄.** 넘으면 책임 단위로 분리한다.
- **함수 최대 30줄.** 넘으면 작은 함수로 쪼갠다. 함수 이름으로 의도가 드러나야 한다.

### 코딩 스타일
- **타입 힌트 필수** — 인자와 반환값에 모두 표기한다.
- **f-string 사용** — `%` 포매팅, `.format()` 쓰지 않는다.
- **공개 함수에 한 줄 docstring** — "무엇을 하는지"가 아니라 "왜/어떻게 쓰는지" 위주로.
- **하드코딩 금지** — 경로·호스트·자격증명은 반드시 `env/` 파일에서 읽는다.
- **주석은 이유가 명확할 때만** — 코드 자체로 설명되면 주석 없이 둔다.

### 프로젝트 레이아웃 규칙
```
utils/          # 프로젝트 전반에서 재사용하는 헬퍼 (env 로딩 등)
<domain>/       # 기능 단위 폴더 (db/, video/, label/ …)
  connection.py / client.py  # 외부 리소스 연결
  queries.py / service.py    # 핵심 로직
  export.py / io.py          # 입출력 변환
  cli.py                     # argparse 진입점
```

---

## 환경 변수 (`env/`)

로컬 실행 환경은 `env/` 디렉토리의 `.env` 파일로 관리한다. 스크립트나 코드에서 호스트명, 경로, 자격증명을 하드코딩하지 말고 반드시 이 파일들에서 읽어온다.

| 파일 | 목적 | 주요 변수 |
|------|------|-----------|
| `env/db.env` | MySQL 연결 정보 | `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` |
| `env/dir.env` | 네트워크 공유폴더 경로 | `ROOT_VIDEO_DIR` |
| `env/python.env` | Python 런타임 및 가상환경 경로 | `PYTHON_PATH`, `VENV_PATH` |
| `env/api.env` | 외부 LLM API 키 | `GEMINI_API_KEY`, `OPENAI_API_KEY`(`generation/v5_m0_m3` 비전 OCR·브랜드 리서치용), `ANTHROPIC_API_KEY`(`generation/v5_m0_m3 --llm_backend api` 전용 — 기본값 `cli`(claude -p)는 불필요) |
| `env/v5_category_db.env` | `generation/v5_m0_m3` 카테고리 분류용 — 소스 shortform-pipeline RDS 의 `category` 테이블 읽기 전용 접속 정보(이 프로젝트 자체 DB 와 무관) | `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` |

**새 환경 변수가 필요하면** 성격에 맞는 파일에 추가하고, 파일이 없으면 새 `.env` 파일을 만든다. `env/README.md`도 함께 업데이트한다.
