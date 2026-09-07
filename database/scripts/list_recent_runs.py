"""v5runs 테이블에서 최근 run 목록을 조회한다.

사용 예:
  python scripts/list_recent_runs.py --limit 20
  python scripts/list_recent_runs.py --since 2026-09-01 --until 2026-09-04
  python scripts/list_recent_runs.py --limit 10 --status done --json

결과 저장 (export_run_assets.py --file 로 그대로 넘길 수 있음):
  python scripts/list_recent_runs.py --limit 20 --save runs.json   # 전체 정보 JSON
  python scripts/list_recent_runs.py --limit 20 --save runs.csv    # 전체 정보 CSV
  python scripts/list_recent_runs.py --limit 20 --save runids.txt  # runid만 한 줄씩
"""
import argparse
import csv
import json
import sys
from pathlib import Path

from db_config import get_connection

BASE_QUERY = """
SELECT
    r.runid,
    r.title,
    r.status,
    r.processstatus,
    r.confirmyn,
    r.regdt,
    r.updatedt,
    r.businessid,
    r.adcategorygroupid,
    (SELECT COUNT(*) FROM v5storyboards sb WHERE sb.runid = r.runid) AS storyboard_count,
    (SELECT COUNT(*) FROM v5videos v WHERE v.runid = r.runid) AS video_count
FROM v5runs r
"""


def parse_args():
    p = argparse.ArgumentParser(description="최근 run 목록 조회")
    p.add_argument("--limit", type=int, default=20, help="조회할 최대 건수 (기본 20)")
    p.add_argument("--since", help="조회 시작일 (YYYY-MM-DD), regdt 기준")
    p.add_argument("--until", help="조회 종료일 (YYYY-MM-DD), regdt 기준")
    p.add_argument("--status", help="status 필터 (예: done, created)")
    p.add_argument("--json", action="store_true", help="JSON으로 출력 (기본은 표 형식)")
    p.add_argument(
        "--save",
        help=(
            "조회 결과를 파일로 저장. 확장자에 따라 형식 결정: "
            ".json=전체 정보 JSON, .csv=전체 정보 CSV, 그 외(.txt 등)=runid만 한 줄씩"
        ),
    )
    return p.parse_args()


def build_query(args):
    where = []
    params = []

    if args.since:
        where.append("r.regdt >= %s")
        params.append(args.since)
    if args.until:
        where.append("r.regdt < DATE_ADD(%s, INTERVAL 1 DAY)")
        params.append(args.until)
    if args.status:
        where.append("r.status = %s")
        params.append(args.status)

    query = BASE_QUERY
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY r.regdt DESC"
    if args.limit and not (args.since or args.until):
        query += " LIMIT %s"
        params.append(args.limit)
    elif args.limit:
        # 기간 지정 + limit 동시 사용 시 상한으로 적용
        query += " LIMIT %s"
        params.append(args.limit)

    return query, params


def print_table(rows):
    if not rows:
        print("결과 없음")
        return
    headers = list(rows[0].keys())
    widths = {h: max(len(h), max(len(str(r[h])) for r in rows)) for h in headers}
    line = " | ".join(h.ljust(widths[h]) for h in headers)
    print(line)
    print("-" * len(line))
    for r in rows:
        print(" | ".join(str(r[h]).ljust(widths[h]) for h in headers))
    print(f"\n총 {len(rows)}건")


def save_rows(rows, path: str):
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    suffix = dest.suffix.lower()

    if suffix == ".json":
        dest.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    elif suffix == ".csv":
        with open(dest, "w", newline="", encoding="utf-8-sig") as f:
            if rows:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
    else:
        dest.write_text("\n".join(r["runid"] for r in rows) + ("\n" if rows else ""), encoding="utf-8")

    print(f"저장됨: {dest.resolve()} ({len(rows)}건)")


def main():
    args = parse_args()
    query, params = build_query(args)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
    finally:
        conn.close()

    for r in rows:
        r["regdt"] = str(r["regdt"])
        r["updatedt"] = str(r["updatedt"])

    if args.json:
        json.dump(rows, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        print_table(rows)

    if args.save:
        save_rows(rows, args.save)


if __name__ == "__main__":
    main()
