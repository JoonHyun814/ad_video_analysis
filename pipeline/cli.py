import argparse
import dataclasses
import json
import sys
from pathlib import Path

from pipeline.cuts import detect_cuts
from pipeline.keyframe import extract_keyframes
from pipeline.ocr import run_ocr_batch
from pipeline.video_loader import get_video_info

_OUTPUT_ROOT = Path("output")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="영상 분석 파이프라인 (컷 감지 → keyframe → OCR)")
    parser.add_argument("--video_id", type=int, required=True, help="video_uploads.id")
    parser.add_argument("--threshold", type=float, default=27.0, help="컷 감지 민감도 (낮을수록 민감, 기본 27.0)")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    out = _OUTPUT_ROOT / str(args.video_id)

    print(f"[1/4] 영상 정보 조회 중... (video_id={args.video_id})")
    video_path, meta = get_video_info(args.video_id)
    print(f"      파일: {video_path}")

    print(f"[2/4] 컷 감지 중... (threshold={args.threshold})")
    cuts = detect_cuts(video_path, threshold=args.threshold)
    _save_json(out / "cuts.json", [dataclasses.asdict(c) for c in cuts])
    print(f"      컷 수: {len(cuts)}  →  {out / 'cuts.json'}")

    print("[3/4] Keyframe 추출 중...")
    keyframes = extract_keyframes(video_path, cuts, out / "keyframes")
    print(f"      추출된 keyframe: {len(keyframes)}장  →  {out / 'keyframes'}")

    print("[4/4] OCR 진행 중...")
    ocr_results = run_ocr_batch(keyframes)
    _save_json(out / "ocr.json", ocr_results)
    print(f"      완료  →  {out / 'ocr.json'}")


def _save_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
