"""홀드아웃 video_id 목록으로 두 산출물 디렉토리(before/after)의 구조 품질을 비교한다.

파인튜닝 전(base 모델) 산출물과 후(LoRA 적용) 산출물을 같은 video_id 세트로 놓고
schema_check.check_video_structure() 결과를 집계해 컷 수 일치율·필드 완전성이
실제로 개선됐는지 수치로 비교한다. 프레임 단위 시각 정확도(색상·환각 등)는 이 스크립트의
범위 밖이며, 별도의 사람/LLM 검수가 필요하다.

사용법:
    python -m train_pipeline.compare_outputs \
        --before_dir output/qwen3.6-cc --after_dir output/qwen3.6-cc-lora \
        --holdout_manifest train_pipeline/data/total_20260710/holdout_video_ids.json
"""

import argparse
import json
from pathlib import Path

from train_pipeline.schema_check import check_video_structure

_RATE_KEYS = ("scene_count_ok_rate", "cut_count_ok_rate", "scenario_present_rate", "scenario_scenes_ok_rate")


def _video_ids(args: argparse.Namespace) -> list[str]:
    if args.holdout_manifest:
        payload = json.loads(args.holdout_manifest.read_text(encoding="utf-8"))
        return payload["holdout_ids"]
    return args.video_ids


def _collect(base_dir: Path, video_ids: list[str]) -> list[dict]:
    return [check_video_structure(base_dir / vid) for vid in video_ids if (base_dir / vid).exists()]


def _summarize(reports: list[dict]) -> dict:
    n = len(reports) or 1
    return {
        "n_videos": len(reports),
        "scene_count_ok_rate": sum(r["scene_count_ok"] for r in reports) / n,
        "cut_count_ok_rate": sum(r["cut_count_ok"] for r in reports) / n,
        "scenario_present_rate": sum(r["scenario_present"] for r in reports) / n,
        "scenario_scenes_ok_rate": sum(r["scenario_scenes_ok"] for r in reports) / n,
        "avg_scene_field_gaps": sum(r["scene_field_gaps"] for r in reports) / n,
        "avg_cut_field_gaps": sum(r["cut_field_gaps"] for r in reports) / n,
    }


def _print_comparison(before: dict, after: dict) -> None:
    print(f"{'항목':28s} {'before':>10s} {'after':>10s}")
    for key in before:
        b, a = before[key], after[key]
        if key == "n_videos":
            print(f"{key:28s} {b:>10d} {a:>10d}")
        elif key in _RATE_KEYS:
            print(f"{key:28s} {b:>9.1%} {a:>9.1%}")
        else:
            print(f"{key:28s} {b:>10.2f} {a:>10.2f}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="before/after 산출물 구조 품질 비교")
    parser.add_argument("--before_dir", type=Path, required=True, help="파인튜닝 전 산출물 루트")
    parser.add_argument("--after_dir", type=Path, required=True, help="파인튜닝 후 산출물 루트")
    parser.add_argument("--holdout_manifest", type=Path, default=None, help="train_pipeline.holdout 매니페스트 경로")
    parser.add_argument("--video_ids", nargs="+", default=[], help="holdout_manifest 대신 직접 video_id 나열")
    parser.add_argument("--report_out", type=Path, default=None, help="비디오별 상세 리포트 JSON 저장 경로")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    ids = _video_ids(args)
    if not ids:
        raise SystemExit("--holdout_manifest 또는 --video_ids 중 하나는 필요합니다")

    before_reports = _collect(args.before_dir, ids)
    after_reports = _collect(args.after_dir, ids)
    _print_comparison(_summarize(before_reports), _summarize(after_reports))

    if args.report_out:
        payload = {"before": before_reports, "after": after_reports}
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n상세 리포트 저장: {args.report_out}")


if __name__ == "__main__":
    main()
