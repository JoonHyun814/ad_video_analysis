import csv
from pathlib import Path

from db.queries import fetch_table


def save_to_csv(table_name: str, output_dir: Path = Path(".")) -> Path:
    """table_name 전체를 output_dir/<table_name>.csv 로 저장하고 경로를 반환한다."""
    columns, rows = fetch_table(table_name)
    output_path = output_dir / f"{table_name}.csv"
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)
    return output_path
