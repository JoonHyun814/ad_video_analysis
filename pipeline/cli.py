import argparse
import dataclasses
import json
from pathlib import Path

from pipeline.cuts import detect_cuts
from pipeline.keyframe import extract_keyframes
from pipeline.ocr import run_ocr_batch
from pipeline.video_loader import get_video_info

_OUTPUT_ROOT = Path("output")
_CUT_BACKENDS = ("transnetv2", "scenedetect")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="영상 분석 파이프라인 (컷 감지 → keyframe → OCR)")
    parser.add_argument("--video_id", type=int, required=True, help="video_uploads.id")
    parser.add_argument(
        "--cut_backend",
        choices=_CUT_BACKENDS,
        default="transnetv2",
        help="컷 감지 백엔드 (기본: transnetv2)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="컷 감지 민감도 (transnetv2: 0.3 기본, scenedetect: 27.0 기본)",
    )
    parser.add_argument(
        "--out_dir",
        type=Path,
        default=None,
        help=f"결과 저장 디렉토리 (기본: {_OUTPUT_ROOT}/<video_id>)",
    )
    return parser


def _detect(video_path: Path, backend: str, threshold: float | None) -> list:
    if backend == "transnetv2":
        from pipeline.transnetv2_cuts import detect_cuts_transnetv2

        thr = threshold if threshold is not None else 0.3
        return detect_cuts_transnetv2(video_path, threshold=thr)
    else:
        thr = threshold if threshold is not None else 27.0
        return detect_cuts(video_path, threshold=thr)


def main() -> None:
    args = _build_parser().parse_args()
    out = args.out_dir if args.out_dir is not None else _OUTPUT_ROOT / str(args.video_id)

    print(f"[1/4] 영상 정보 조회 중... (video_id={args.video_id})")
    video_path, meta = get_video_info(args.video_id)
    print(f"      파일: {video_path}")

    print(f"[2/4] 컷 감지 중... (backend={args.cut_backend}, threshold={args.threshold})")
    cuts = _detect(video_path, args.cut_backend, args.threshold)
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
