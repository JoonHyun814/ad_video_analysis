"""video_uploads 테이블을 순회하거나 디렉토리를 스캔하여 CLI를 배치 실행한다.

사용법:
    # pipeline / evaluation — DB에서 ID 조회
    python run_batch.py --video_ids 1-10 --module pipeline
    python run_batch.py --video_ids 1,3,5 --module evaluation -- --parsed_analysis
    python run_batch.py --start_id 1 --module evaluation -- --scenario_evaluation

    # category — DB 불필요, 디렉토리 기반
    python run_batch.py --video_ids 89,100-105 --module category -- --category_analysis --load_vector
    python run_batch.py --video_ids 89,100-105 --module category -- --category_analysis --load_vector --llm_backend gemini
    python run_batch.py --start_id 89 --module category --data_dir output/product_plan/claude -- --category_analysis --load_vector

    # 추가 옵션은 -- 뒤에 전달, 영상 간 대기는 --interval
    python run_batch.py --video_ids 1-20 --interval 60 -- --llm_backend codex
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

_MODULES = {
    "pipeline": "pipeline.cli",
    "evaluation": "evaluation.cli",
    "category": "evaluation.category_cli",
}

# DB 조회 없이 로컬 디렉토리 기반으로 동작하는 모듈
_NO_DB_MODULES = {"category"}

_DEFAULT_CATEGORY_DIR = Path("output/product_plan/claude")


# ── ID 파싱 ────────────────────────────────────────────────────────────────────

def _parse_ids(spec: str) -> list[int]:
    """'1-5,8,10-15' 형식의 문자열을 정렬된 고유 ID 리스트로 변환한다."""
    ids: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            ids.update(range(int(start), int(end) + 1))
        else:
            ids.add(int(part))
    return sorted(ids)


# ── DB 기반 ID 조회 ────────────────────────────────────────────────────────────

def _fetch_existing(ids: list[int]) -> list[int]:
    from db.connection import get_connection
    placeholders = ", ".join(["%s"] * len(ids))
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT id FROM video_uploads WHERE id IN ({placeholders}) ORDER BY id ASC", ids
        )
        return [row[0] for row in cursor.fetchall()]


def _fetch_from(start_id: int) -> list[int]:
    from db.connection import get_connection
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM video_uploads WHERE id >= %s ORDER BY id ASC", (start_id,)
        )
        return [row[0] for row in cursor.fetchall()]


# ── 디렉토리 기반 ID 스캔 (category 모듈용) ────────────────────────────────────

def _scan_dir_ids(data_dir: Path, start_id: int = 0) -> list[int]:
    """data_dir 하위의 숫자 디렉토리를 스캔해 start_id 이상인 ID를 반환한다."""
    if not data_dir.exists():
        print(f"[오류] data_dir 없음: {data_dir}", file=sys.stderr)
        return []
    ids = sorted(
        int(d.name)
        for d in data_dir.iterdir()
        if d.is_dir() and d.name.isdigit() and int(d.name) >= start_id
    )
    return ids


# ── 실행 ───────────────────────────────────────────────────────────────────────

def _run_one(video_id: int, module: str, extra_args: list[str]) -> int:
    cmd = [sys.executable, "-m", _MODULES[module], "--video_id", str(video_id)] + extra_args
    print(f"\n{'='*60}")
    print(f"  video_id={video_id}  [{module}]  {' '.join(cmd[3:])}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    return result.returncode


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    argv = sys.argv[1:]
    if "--" in argv:
        sep = argv.index("--")
        own_argv, extra_args = argv[:sep], argv[sep + 1:]
    else:
        own_argv, extra_args = argv, []

    parser = argparse.ArgumentParser(
        description="pipeline / evaluation / category CLI 배치 실행",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--video_ids", metavar="RANGE",
                       help="실행할 video_id 범위/목록. 예: 1-10 / 1,3,5 / 1-5,8,10-15")
    group.add_argument("--start_id", type=int, metavar="ID",
                       help="이 id 이상의 모든 video를 순서대로 실행")
    parser.add_argument("--module", choices=tuple(_MODULES.keys()), default="pipeline",
                        help="실행 모듈 (기본: pipeline)")
    parser.add_argument("--data_dir", type=Path, default=_DEFAULT_CATEGORY_DIR,
                        help=f"[category] ID 스캔 기준 디렉토리 (기본: {_DEFAULT_CATEGORY_DIR})")
    parser.add_argument("--interval", type=int, default=0,
                        help="영상 간 대기 시간(초). 기본: 0")
    args = parser.parse_args(own_argv)

    # ID 목록 결정
    if args.module in _NO_DB_MODULES:
        if args.video_ids:
            ids = _parse_ids(args.video_ids)
        else:
            ids = _scan_dir_ids(args.data_dir, start_id=args.start_id)
        # category_cli 에 --data_dir 가 없으면 기본값에서 자동 주입
        if "--data_dir" not in extra_args:
            extra_args = ["--data_dir", str(args.data_dir)] + extra_args
    else:
        requested = _parse_ids(args.video_ids) if args.video_ids else None
        if requested is not None:
            ids = _fetch_existing(requested)
            skipped = sorted(set(requested) - set(ids))
            if skipped:
                print(f"DB에 없어 스킵: {skipped}")
        else:
            ids = _fetch_from(args.start_id)

    if not ids:
        print("처리할 video_id가 없습니다.")
        return

    print(f"실행 모듈: {_MODULES[args.module]}")
    print(f"처리 대상: {len(ids)}건  {ids}")
    if extra_args:
        print(f"추가 옵션: {' '.join(extra_args)}")

    fail_ids: list[int] = []
    for i, video_id in enumerate(ids):
        rc = _run_one(video_id, args.module, extra_args)
        if rc != 0:
            print(f"  [경고] video_id={video_id} 종료코드 {rc}")
            fail_ids.append(video_id)

        if args.interval > 0 and i < len(ids) - 1:
            print(f"\n  {args.interval}초 대기 후 다음 (video_id={ids[i + 1]}) 시작...")
            time.sleep(args.interval)

    print(f"\n완료: 성공 {len(ids) - len(fail_ids)}건 / 실패 {len(fail_ids)}건")
    if fail_ids:
        print(f"  실패 ID: {fail_ids}")


if __name__ == "__main__":
    main()
