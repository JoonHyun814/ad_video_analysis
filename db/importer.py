import csv
from pathlib import Path

from db.connection import get_connection


def load_from_csv(
    csv_path: Path,
    table_name: str,
    create_table: bool = False,
) -> int:
    """CSV 파일을 table_name 테이블에 적재하고 삽입된 행 수를 반환한다.

    create_table=True 면 테이블을 DROP → CREATE(모든 컬럼 TEXT) → INSERT 한다.
    create_table=False 면 기존 테이블에 행을 추가(append)한다.
    """
    rows, columns = _read_csv(csv_path)
    if not rows:
        return 0

    with get_connection() as conn:
        cursor = conn.cursor()
        if create_table:
            _recreate_table(cursor, table_name, columns)
        _insert_rows(cursor, table_name, columns, rows)
        conn.commit()

    return len(rows)


# ── 내부 헬퍼 ──────────────────────────────────────────────────────────────────

def _read_csv(csv_path: Path) -> tuple[list[tuple], list[str]]:
    """CSV를 읽어 (행 리스트, 컬럼명 리스트)를 반환한다."""
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        columns = next(reader)
        rows = [tuple(r) for r in reader]
    return rows, columns


def _recreate_table(cursor, table_name: str, columns: list[str]) -> None:
    """테이블을 삭제하고 모든 컬럼을 TEXT 타입으로 재생성한다."""
    cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`")
    col_defs = ", ".join(f"`{c}` TEXT" for c in columns)
    cursor.execute(f"CREATE TABLE `{table_name}` ({col_defs})")


def _insert_rows(cursor, table_name: str, columns: list[str], rows: list[tuple]) -> None:
    """rows 를 table_name 에 일괄 삽입한다."""
    placeholders = ", ".join(["%s"] * len(columns))
    col_names = ", ".join(f"`{c}`" for c in columns)
    sql = f"INSERT INTO `{table_name}` ({col_names}) VALUES ({placeholders})"
    cursor.executemany(sql, rows)
