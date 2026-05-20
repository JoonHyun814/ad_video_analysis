import argparse
import sys

from db.export import save_to_csv
from db.queries import list_tables


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DB 유틸리티")
    parser.add_argument("--table_list", action="store_true", help="테이블 목록 출력")
    parser.add_argument("--save_csv", action="store_true", help="테이블을 CSV로 저장")
    parser.add_argument("--table_name", type=str, metavar="TABLE", help="대상 테이블명")
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


def main() -> None:
    args = _build_parser().parse_args()

    if not any([args.table_list, args.save_csv]):
        _build_parser().print_help()
        return

    if args.table_list:
        _cmd_table_list()

    if args.save_csv:
        _cmd_save_csv(args.table_name)


if __name__ == "__main__":
    main()
