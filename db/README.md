# db 모듈

MySQL DB 연결 및 데이터 조회/추출 유틸리티.

## 파일 구성

| 파일 | 역할 |
|------|------|
| `connection.py` | `env/db.env` 를 읽어 MySQL 연결을 열고 닫는 컨텍스트 매니저 |
| `queries.py` | 테이블 목록 조회, 테이블 전체 데이터 조회 |
| `export.py` | 쿼리 결과를 CSV 파일로 저장 |
| `cli.py` | 커맨드라인 진입점 |

## 사전 준비

1. `env/db.env` 에 DB 접속 정보 입력
2. 가상환경 활성화

```powershell
. .venv\Scripts\Activate.ps1
```

## CLI 사용법

프로젝트 루트에서 실행한다.

### 테이블 목록 출력

```powershell
python -m db.cli --table_list
```

```
video_uploads
labeling_data
users
...
```

### 테이블을 CSV로 저장

```powershell
python -m db.cli --save_csv --table_name <테이블명>
```

현재 디렉토리에 `<테이블명>.csv` 로 저장된다.

```powershell
# 예시
python -m db.cli --save_csv --table_name video_uploads
# → ./video_uploads.csv 생성
```

### 옵션 조합

두 옵션을 동시에 사용할 수 있다.

```powershell
python -m db.cli --table_list --save_csv --table_name labeling_data
```

## 코드에서 직접 사용

```python
from db.queries import list_tables, fetch_table
from db.export import save_to_csv

# 테이블 목록
tables = list_tables()

# 특정 테이블 데이터
columns, rows = fetch_table("video_uploads")

# CSV 저장 (저장 경로 지정 가능)
from pathlib import Path
path = save_to_csv("video_uploads", output_dir=Path("output"))
```
