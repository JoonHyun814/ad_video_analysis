# CLAUDE.md

## 프로젝트 개요

광고 영상 분석 프로젝트. 영상 파일은 네트워크 공유폴더에 저장되며, 메타데이터와 레이블은 MySQL DB에 관리된다.

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

**새 환경 변수가 필요하면** 성격에 맞는 파일에 추가하고, 파일이 없으면 새 `.env` 파일을 만든다. `env/README.md`도 함께 업데이트한다.

---

## 가상환경 (`setup_venv.ps1`)

`setup_venv.ps1`은 `env/python.env`를 읽어 `VENV_PATH`에 가상환경을 생성한다.

```powershell
.\setup_venv.ps1          # 최초 환경 구성
. .venv\Scripts\Activate.ps1   # 가상환경 활성화
```

**패키지를 설치하거나 의존성이 바뀔 때마다** `setup_venv.ps1`에도 반영한다. 예를 들어 `pip install` 명령이 추가되면 스크립트 하단에 해당 설치 단계를 추가한다. 이렇게 해야 환경을 새로 구성할 때 스크립트 한 번으로 재현이 가능하다.

---

## DB 연결

- 호스트: `DB_HOST:DB_PORT` (db.env)
- DB명: `DB_NAME` (db.env)
- 연결 전 `env/db.env`를 파싱해서 사용한다.

---

## 공유폴더

- 경로: `ROOT_VIDEO_DIR` (dir.env)
- DB의 `video_uploads.file_path`는 이 경로를 루트로 하는 상대경로다.
- 절대경로가 필요할 때는 `ROOT_VIDEO_DIR + file_path`로 조합한다.
