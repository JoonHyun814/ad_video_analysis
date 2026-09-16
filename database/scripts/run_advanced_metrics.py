"""이미 처리된 comparison.json 각각에 T2VScore-A/VBench-2.0 심화 지표를 추가 계산해
"advanced_metrics" 키로 병합 저장한다.

run_comparison_pipeline.py 를 다시 돌릴 필요 없이, 이미 받아둔 assets/scenario 를 그대로
재사용한다 — 원본(prompt·스토리보드 이미지)은 DB 에서 다시 조회하고, 재분석 결과는
<unit_dir>/scenario/video<id>/scenario_analysis.json 을 읽는다.

사용 예:
  python scripts/run_advanced_metrics.py --out_dir ../output/postprocessed
  python scripts/run_advanced_metrics.py --out_dir ../output/original --video_source original
"""
import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from advanced_metrics import compute_advanced_metrics  # noqa: E402
from matching import MatchedUnit, fetch_matched_units  # noqa: E402
from unit_lookup import fetch_unit_by_id  # noqa: E402

_UNIT_LOOKUP_LIMIT = 500


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="comparison.json 에 T2VScore-A/VBench-2.0 심화 지표 추가")
    p.add_argument("--out_dir", type=Path, required=True, help="run_comparison_pipeline.py 의 --out_dir 와 동일 경로")
    p.add_argument(
        "--video_source", choices=("postprocessed", "original"), default="postprocessed",
        help="comparison.json 을 만들 때 쓴 --video_source 와 동일해야 스토리보드를 다시 찾을 수 있다",
    )
    p.add_argument("--overwrite", action="store_true", help="이미 advanced_metrics 가 있어도 다시 계산")
    p.add_argument("--timeout", type=int, default=600, help="claude -p 타임아웃(초, 기본 600)")
    return p.parse_args()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    comparison_paths = sorted(args.out_dir.glob("*/video*/comparison.json"))
    print(f"comparison.json {len(comparison_paths)}건 발견 (video_source={args.video_source})")

    units_by_key = _index_units(args.video_source)
    results = [_process_one(path, units_by_key, args) for path in comparison_paths]
    _print_and_save_summary(args.out_dir, results)


def _process_one(path: Path, units_by_key: dict[tuple, MatchedUnit], args: argparse.Namespace) -> dict:
    print(f"\n{path}")
    comparison = json.loads(path.read_text(encoding="utf-8"))
    if "advanced_metrics" in comparison and not args.overwrite:
        print("      이미 계산됨 - 스킵")
        return {"path": str(path), "skipped": True}

    key = (comparison["run_id"], comparison["video_id"], comparison["storyboard_id"])
    unit = units_by_key.get(key) or fetch_unit_by_id(*key, comparison["video_source"])
    if unit is None:
        print("      매칭 유닛을 DB 에서 다시 찾지 못함 - 스킵 (원본 자체가 삭제됐을 수 있음)")
        return {"path": str(path), "error": "unit_not_found"}

    scenario = _load_scenario(path.parent, comparison["video_id"])
    if scenario is None:
        print("      scenario_analysis.json 없음 - 스킵")
        return {"path": str(path), "error": "scenario_missing"}

    advanced = compute_advanced_metrics(unit, scenario, path.parent / "assets" / "images", args.timeout)
    comparison["advanced_metrics"] = advanced
    path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    if advanced["parse_failed"]:
        print("      claude -p 응답 파싱 실패 - advanced_metrics 가 비어있다 (재실행 필요)")
        return {"path": str(path), "error": "parse_failed"}
    print(
        f"      완료 (t2vscore_a={advanced['t2vscore_a']['score']}, "
        f"vbench2 적용 가능 {advanced['vbench2_summary']['applicable_dimensions']}"
        f"/{advanced['vbench2_summary']['total_dimensions']}차원, "
        f"평균={advanced['vbench2_summary']['avg_score']})"
    )
    return {"path": str(path), "ok": True}


def _load_scenario(unit_dir: Path, video_id: int) -> dict | None:
    scenario_path = unit_dir / "scenario" / f"video{video_id}" / "scenario_analysis.json"
    if not scenario_path.exists():
        return None
    return json.loads(scenario_path.read_text(encoding="utf-8"))


def _index_units(video_source: str) -> dict[tuple, MatchedUnit]:
    units = fetch_matched_units(limit=_UNIT_LOOKUP_LIMIT, video_source=video_source)
    return {(u.run_id, u.video_id, u.storyboard_id): u for u in units}


def _print_and_save_summary(out_dir: Path, results: list[dict]) -> None:
    ok = sum(1 for r in results if r.get("ok"))
    skipped = sum(1 for r in results if r.get("skipped"))
    errors = sum(1 for r in results if "error" in r)
    print(f"\n완료: 성공 {ok}건 / 스킵 {skipped}건 / 실패 {errors}건 (총 {len(results)}건)")
    (out_dir / "advanced_metrics_summary.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
