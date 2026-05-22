"""video_uploads 테이블을 순회하며 pipeline.cli 를 실행한다.

사용법:
    # 특정 ID 범위/목록 지정 (DB에 없는 ID는 자동 스킵)
    python run_batch.py --video_ids 1-10
    python run_batch.py --video_ids 1,3,5,7
    python run_batch.py --video_ids 1-5,8,10-15

    # start_id 이상의 전체 실행
    python run_batch.py --start_id 1

    # pipeline 옵션은 -- 뒤에 전달
    python run_batch.py --video_ids 1-20 --interval 60 -- --llm_backend codex --max_cuts 10
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

from db.connection import get_connection


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


def _fetch_existing(ids: list[int]) -> list[int]:
    """주어진 ID 목록 중 video_uploads에 실제 존재하는 것만 오름차순으로 반환한다."""
    placeholders = ", ".join(["%s"] * len(ids))
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT id FROM video_uploads WHERE id IN ({placeholders}) ORDER BY id ASC",
            ids,
        )
        return [row[0] for row in cursor.fetchall()]


def _fetch_from(start_id: int) -> list[int]:
    """video_uploads에서 start_id 이상인 id를 오름차순으로 반환한다."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM video_uploads WHERE id >= %s ORDER BY id ASC",
            (start_id,),
        )
        return [row[0] for row in cursor.fetchall()]


def _run_pipeline(video_id: int, extra_args: list[str]) -> int:
    cmd = [sys.executable, "-m", "pipeline.cli", "--video_id", str(video_id)] + extra_args
    print(f"\n{'='*60}")
    print(f"  video_id={video_id}  명령: {' '.join(cmd)}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    return result.returncode


def main() -> None:
    # '--' 이후 인자는 pipeline.cli 에 그대로 전달
    argv = sys.argv[1:]
    if "--" in argv:
        sep = argv.index("--")
        own_argv, extra_args = argv[:sep], argv[sep + 1:]
    else:
        own_argv, extra_args = argv, []

    parser = argparse.ArgumentParser(
        description="video_uploads를 순회하며 pipeline.cli를 실행",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--video_ids",
        type=str,
        metavar="RANGE",
        help="실행할 video_id 범위/목록. 예: 1-10  /  1,3,5  /  1-5,8,10-15",
    )
    group.add_argument(
        "--start_id",
        type=int,
        metavar="ID",
        help="이 id 이상의 모든 video를 순서대로 실행",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=0,
        help="영상 간 대기 시간(초). 기본: 0",
    )
    args = parser.parse_args(own_argv)

    if args.video_ids:
        requested = _parse_ids(args.video_ids)
        ids = _fetch_existing(requested)
        skipped = sorted(set(requested) - set(ids))
        if skipped:
            print(f"DB에 없어 스킵: {skipped}")
    else:
        ids = _fetch_from(args.start_id)

    if not ids:
        print("처리할 video_id가 없습니다.")
        return

    print(f"처리 대상: {len(ids)}건  {ids}")
    if extra_args:
        print(f"pipeline 추가 옵션: {' '.join(extra_args)}")

    for i, video_id in enumerate(ids):
        rc = _run_pipeline(video_id, extra_args)
        if rc != 0:
            print(f"  [경고] video_id={video_id} 파이프라인 종료코드 {rc}")

        if args.interval > 0 and i < len(ids) - 1:
            print(f"\n  {args.interval}초 대기 후 다음 영상 (video_id={ids[i + 1]}) 시작...")
            time.sleep(args.interval)

    print("\n모든 영상 처리 완료.")


if __name__ == "__main__":
    main()
