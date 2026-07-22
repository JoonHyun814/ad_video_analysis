"""parsed_analysis.json 을 VideoLabelingTool 외부 스키마(wrapped)로 변환한다.

기존 convert.py(`--mode parsed`)는 parsed_analysis 내부 필드를 재가공해
claude_preprocessed_v1 의 평탄화된 스키마로 출력한다.
v2 는 재가공 없이 parsed_analysis 전체를 `parsed` 키 아래로 감싸고,
상위에 `video_id` / `original_filename` / `model_cuts` 등 외부 메타만 부여한다.
"""
import argparse
import json
from pathlib import Path

from evaluation.convert.convert import _iter_video_dirs, _lookup_filename


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="parsed_analysis → wrapped 스키마 변환 (v2)")
    p.add_argument("--video_dir", type=Path, required=True, help="<video_id> 하위 폴더들이 들어있는 루트 디렉토리")
    p.add_argument("--out_dir", type=Path, required=True, help="결과 JSON 저장 디렉토리 (<video_id>.json 으로 저장)")
    return p


def load_parsed(video_dir: Path) -> dict:
    """video_dir/parsed_analysis.json 을 로드한다."""
    path = video_dir / "parsed_analysis.json"
    if not path.exists():
        raise FileNotFoundError(f"parsed_analysis.json 없음: {video_dir}")
    return json.loads(path.read_text(encoding="utf-8"))


def convert(parsed: dict, video_id: int, video_filename: str) -> dict:
    """parsed_analysis 를 외부 스키마(wrapped)로 감싼다."""
    return {
        "video_id": video_id,
        "original_filename": video_filename,
        "ad_id": parsed.get("ad_id", ""),
        "duration": parsed.get("duration"),
        "fps": None,
        "inference_time_sec": None,
        "stt_segments": None,
        "stt_full_text": None,
        "gpu_memory_gb": None,
        "transnet_cuts": None,
        "model_cuts": _build_model_cuts(parsed),
        "parsed": parsed,
        "parse_success": not bool(parsed.get("error")),
        "human_label": None,
        "match": None,
    }


def _build_model_cuts(parsed: dict) -> list[dict]:
    """parsed.cuts 의 cut_id/start_sec/end_sec 를 외부 스키마 형태로 추린다."""
    cuts = parsed.get("cuts") or []
    return [
        {"cut_num": c.get("cut_id"), "start": c.get("start_sec"), "end": c.get("end_sec")}
        for c in cuts
    ]


def _process(video_dir: Path, out_dir: Path) -> None:
    try:
        video_id = int(video_dir.name)
    except ValueError:
        print(f"      건너뜀(폴더명이 정수 아님): {video_dir.name}")
        return
    try:
        video_filename = _lookup_filename(video_id)
    except Exception as e:
        print(f"      [{video_id}] 영상 파일명 조회 실패 ({e}) — 빈 문자열로 진행")
        video_filename = ""
    parsed = load_parsed(video_dir)
    payload = convert(parsed, video_id, video_filename)
    out_path = out_dir / f"{video_id}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"      [{video_id}] saved → {out_path}")


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    if not args.video_dir.is_dir():
        raise SystemExit(f"오류: --video_dir 가 디렉토리가 아님: {args.video_dir}")

    targets = _iter_video_dirs(args.video_dir, "parsed_analysis.json")
    if not targets:
        raise SystemExit(f"오류: parsed_analysis.json 을 포함한 하위 폴더 없음: {args.video_dir}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    print(f"변환 대상: {len(targets)}개 (v2 wrapped)")
    for i, vdir in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] {vdir.name}")
        try:
            _process(vdir, args.out_dir)
        except Exception as e:
            print(f"      실패: {e}")
    print(f"\n완료 → {args.out_dir}")


if __name__ == "__main__":
    main()
