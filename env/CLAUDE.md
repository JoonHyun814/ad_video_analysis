# env/

환경 변수 파일 모음. **경로·DB·자격증명·모델 경로는 절대 코드에 하드코딩하지 않는다.**

| 파일 | 목적 | 주요 변수 |
|------|------|-----------|
| `python.env` | Python 런타임·가상환경 경로 | `PYTHON_PATH`, `VENV_PATH`, `TRAIN_VENV_PATH` |
| `data.env` | 데이터 경로 | `DATA_ROOT` (출력 루트), `SOURCE_ROOT` (읽기 전용 원본 소스) |
| `model.env` | 로컬 모델 루트 경로 | `MODEL_ROOT` (`D:\models`) |
| `db.env` | DB 접속 정보 | `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` |
| `ssh.env` | 원격 서버 SSH 접속 및 SSHFS 마운트 설정 | `SSH_HOST`, `SSH_USER`, `SSH_PASSWORD`, `REMOTE_VIDEO_DIR`, `SSHFS_MOUNT_DRIVE`, `SSH_TUNNEL_LOCAL_PORT` |
| `api.env` | 외부 LLM API 키 | `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` |
| `v5_category_db.env` | generation 카테고리 분류용 외부 RDS (읽기 전용) | `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` |

새 환경 변수가 필요하면 성격에 맞는 파일에 추가하고 이 파일도 업데이트한다.
