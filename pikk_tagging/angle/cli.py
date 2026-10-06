"""카메라 앵글 분류 파이프라인 CLI.

python -m pikk_tagging.angle.cli --video path/to/video.mp4
python -m pikk_tagging.angle.cli --video path/to/video.mp4 --step 15 --out_dir C:/outputs/angle/hough_lines
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from pikk_tagging.angle.analyzer import analyze_video
from pikk_tagging.angle.classifier import temporal_smooth
from pikk_tagging.angle.io import save_results

_DEFAULT_OUT = Path(r"C:\Users\llm\workspace\outputs\pikk_output\angle\hough_lines")


def _run(video: Path, step: int, min_frames: int, out_dir: Path) -> None:
    print(f"분석 시작: {video.name}  step={step}")
    result           = analyze_video(video, step=step)
    result["frames"] = temporal_smooth(result["frames"], step=step, min_frames=min_frames)

    video_id = video.stem
    out_path = save_results(result, out_dir / video_id)

    counts = Counter(f["label"] for f in result["frames"])
    print(f"완료: {out_path}")
    print("  레이블 분포:", dict(counts.most_common()))


def main() -> None:
    p = argparse.ArgumentParser(description="카메라 앵글 분류 파이프라인")
    p.add_argument("--video",      required=True, help="입력 영상 경로")
    p.add_argument("--step",       type=int, default=30, help="분석 간격 (프레임 수)")
    p.add_argument("--min_frames", type=int, default=30, help="최소 지속 프레임 (temporal filter)")
    p.add_argument("--out_dir",    default=str(_DEFAULT_OUT), help="출력 루트 디렉토리")
    args = p.parse_args()

    video = Path(args.video)
    if not video.exists():
        sys.exit(f"오류: 영상 파일 없음 — {video}")

    _run(video, args.step, args.min_frames, Path(args.out_dir))


if __name__ == "__main__":
    main()
