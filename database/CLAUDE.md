# database/

영상 분석 결과 저장·조회용 DB 모음. 3개 서브모듈로 구성된다.

각 서브모듈 작업 전 해당 CLAUDE.md 만 읽어라.

| 서브모듈 | 역할 | CLAUDE.md |
|----------|------|-----------|
| `video_db/` | 영상 ID 및 메타데이터 관리 (MySQL) | video_db/CLAUDE.md |
| `vector_db/` | 임베딩 벡터 저장·검색 (ChromaDB) | vector_db/CLAUDE.md |
| `pikk_db/` | Pikk 태깅 결과 저장·조회 | pikk_db/CLAUDE.md |

> 서브폴더에 CLAUDE.md 가 아직 없으면 `database/README.md` 와 루트의 `db/README.md` 를 확인한다.
> 기존 레거시 코드는 루트의 `db/` 에 있다.

---

## env 의존

DB 접속 정보는 코드에 하드코딩하지 않는다. 반드시 `env/db.env` 에서 읽는다.
