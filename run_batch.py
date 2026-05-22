"""video_uploads 테이블을 id 순으로 순회하며 pipeline.cli 를 주기적으로 실행한다.

사용법:
    python run_batch.py --start_id 1 --interval 300 [pipeline 옵션...]

pipeline 옵션은 -- 뒤에 그대로 전달된다.
    python run_batch.py --start_id 1 --interval 60 -- --llm_backend codex --max_cuts 10
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

from db.connection import get_connection


def _fetch_ids_from(start_id: int) -> list[int]:
    """video_uploads 에서 start_id 이상인 id를 오름차순으로 반환한다."""
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
    parser = argparse.ArgumentParser(
        description="video_uploads를 순회하며 pipeline.cli를 주기 실행",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--start_id", type=int, required=True, help="시작 video_id")
    parser.add_argument(
        "--interval",
        type=int,
        default=0,
        help="영상 간 대기 시간(초). 0이면 즉시 다음 영상으로 진행 (기본: 0)",
    )

    # '--' 이후 인자는 pipeline.cli 에 그대로 전달
    argv = sys.argv[1:]
    if "--" in argv:
        sep = argv.index("--")
        own_argv, extra_args = argv[:sep], argv[sep + 1:]
    else:
        own_argv, extra_args = argv, []

    args = parser.parse_args(own_argv)

    ids = _fetch_ids_from(args.start_id)
    if not ids:
        print(f"video_uploads 에서 id >= {args.start_id} 인 행이 없습니다.")
        return

    print(f"처리 대상: {len(ids)}건  (id {ids[0]} ~ {ids[-1]})")
    if extra_args:
        print(f"pipeline 추가 옵션: {' '.join(extra_args)}")

    for i, video_id in enumerate(ids):
        rc = _run_pipeline(video_id, extra_args)
        if rc != 0:
            print(f"  [경고] video_id={video_id} 파이프라인 종료코드 {rc}")

        if args.interval > 0 and i < len(ids) - 1:
            next_id = ids[i + 1]
            print(f"\n  {args.interval}초 대기 후 다음 영상 (video_id={next_id}) 시작...")
            time.sleep(args.interval)

    print("\n모든 영상 처리 완료.")


if __name__ == "__main__":
    main()
