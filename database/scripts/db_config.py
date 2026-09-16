"""공용 DB 접속 헬퍼. 접속 정보는 환경변수(.env)에서 읽는다."""
import os

import pymysql
from dotenv import load_dotenv

load_dotenv()


def get_connection(database: str | None = None):
    return pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", 3306)),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=database or os.environ.get("DB_NAME"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
    )
