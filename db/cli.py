import argparse
import sys
from pathlib import Path

from db.export import save_to_csv
from db.queries import list_tables


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DB 유틸리티")
    parser.add_argument("--table_list", action="store_true", help="테이블 목록 출력")
    parser.add_argument("--save_csv", action="store_true", help="테이블을 CSV로 저장")
    parser.add_argument("--load_csv", action="store_true", help="CSV 파일을 테이블에 적재")
    parser.add_argument("--table_name", type=str, metavar="TABLE", help="대상 테이블명")
    parser.add_argument("--csv_path", type=Path, metavar="CSV", help="적재할 CSV 파일 경로 (--load_csv 필수)")
    parser.add_argument(
        "--create_table",
        action="store_true",
        help="테이블을 DROP 후 CSV 헤더 기준으로 재생성(모든 컬럼 TEXT). 미지정 시 기존 테이블에 행 추가",
    )
    return parser


def _cmd_table_list() -> None:
    for name in list_tables():
        print(name)


def _cmd_save_csv(table_name: str | None) -> None:
    if not table_name:
        print("오류: --save_csv 사용 시 --table_name 을 지정해야 합니다.", file=sys.stderr)
        sys.exit(1)
    path = save_to_csv(table_name)
    print(f"저장 완료: {path}")


def _cmd_load_csv(csv_path: Path | None, table_name: str | None, create_table: bool) -> None:
    if not csv_path or not table_name:
        print("오류: --load_csv 사용 시 --csv_path 와 --table_name 을 모두 지정해야 합니다.", file=sys.stderr)
        sys.exit(1)
    if not csv_path.exists():
        print(f"오류: CSV 파일을 찾을 수 없습니다: {csv_path}", file=sys.stderr)
        sys.exit(1)

    from db.importer import load_from_csv
    count = load_from_csv(csv_path, table_name, create_table=create_table)
    action = "생성 후 적재" if create_table else "적재"
    print(f"{action} 완료: {table_name}  ({count}행)")


def main() -> None:
    args = _build_parser().parse_args()

    if not any([args.table_list, args.save_csv, args.load_csv]):
        _build_parser().print_help()
        return

    if args.table_list:
        _cmd_table_list()

    if args.save_csv:
        _cmd_save_csv(args.table_name)

    if args.load_csv:
        _cmd_load_csv(args.csv_path, args.table_name, args.create_table)


if __name__ == "__main__":
    main()
