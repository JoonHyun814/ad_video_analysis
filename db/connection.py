from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import mysql.connector
import mysql.connector.connection

from utils.env_loader import load_env

_ENV_PATH = Path(__file__).parent.parent / "env" / "db.env"


def _build_config() -> dict[str, object]:
    e = load_env(_ENV_PATH)
    return {
        "host": e["DB_HOST"],
        "port": int(e["DB_PORT"]),
        "user": e["DB_USER"],
        "password": e["DB_PASSWORD"],
        "database": e["DB_NAME"],
    }


@contextmanager
def get_connection() -> Generator[mysql.connector.connection.MySQLConnection, None, None]:
    """db.env 를 읽어 MySQL 연결을 열고 컨텍스트 종료 시 닫는다."""
    conn = mysql.connector.connect(**_build_config())
    try:
        yield conn
    finally:
        conn.close()
