from db.connection import get_connection


def list_tables() -> list[str]:
    """현재 DB의 테이블 이름 목록을 반환한다."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES")
        return [row[0] for row in cursor.fetchall()]


def fetch_table(table_name: str) -> tuple[list[str], list[tuple]]:
    """table_name 의 전체 데이터를 (컬럼명 리스트, 행 리스트) 형태로 반환한다."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM `{table_name}`")
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
    return columns, rows
