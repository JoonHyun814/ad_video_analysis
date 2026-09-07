"""prompt+스토리보드 이미지+영상이 모두 있는 데이터에 대해 scenario_analysis 생성 → 원본 비교를
일괄 수행한다.

매칭 유닛(run_id, video_id)마다:
  1) 원본 프롬프트·스토리보드 이미지·영상을 내려받는다        → {run_id}/video{id}/assets/
  2) 영상으로 scenario_analysis 를 생성한다 (pipeline.cli)   → {run_id}/video{id}/scenario/
  3) scenario_analysis 를 원본과 비교해 요인별 판정을 저장한다 → {run_id}/video{id}/comparison.json

이미 처리된 유닛(comparison.json 존재)은 건너뛴다 — 중간에 중단돼도 재실행 시 이어서 처리된다.

사용 예:
  python scripts/run_comparison_pipeline.py --limit 20 --out_dir ../output
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from utils.io_checks import is_parse_failed, require_valid_json  # noqa: E402

from compare_scenario import compare_scenario  # noqa: E402
from fetch_assets import fetch_unit_assets  # noqa: E402
from matching import MatchedUnit, fetch_matched_units  # noqa: E402

_LLM_BACKENDS = ("claude", "codex", "qwen", "gemini")
_PIPELINE_TIMEOUT_SEC = 3600


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="prompt+이미지+영상 매칭 데이터 scenario 생성·비교 파이프라인")
    p.add_argument("--limit", type=int, default=20, help="처리할 매칭 건수 (기본 20)")
    p.add_argument("--out_dir", type=Path, required=True, help="결과 저장 루트 (run_id 하위 폴더 생성)")
    p.add_argument("--llm_backend", choices=_LLM_BACKENDS, default="claude", help="scenario_analysis 생성 LLM 백엔드")
    p.add_argument(
        "--max_cuts", type=int, default=50,
        help="scenario 생성 시 최대 컷 수 상한 (기본 50). pipeline.cli 기본값(10)보다 커야 "
             "컷수 비교가 병합으로 왜곡되지 않는다",
    )
    p.add_argument("--overwrite_assets", action="store_true", help="이미 내려받은 자산도 다시 다운로드")
    return p.parse_args()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    units = fetch_matched_units(args.limit)
    print(f"매칭된 유닛 {len(units)}건 (요청 --limit {args.limit}, prompt+이미지+영상 모두 있는 건만 집계)")

    results: list[dict] = []
    for i, unit in enumerate(units, 1):
        print(f"\n[{i}/{len(units)}] run={unit.run_id} video={unit.video_id} (concept {unit.concept_index})")
        try:
            results.append(_process_unit(unit, args))
        except (Exception, SystemExit) as e:
            print(f"      실패: {e}")
            results.append({"run_id": unit.run_id, "video_id": unit.video_id, "error": str(e)})
        _save_summary(args.out_dir, results)

    ok = sum(1 for r in results if "error" not in r)
    print(f"\n완료: {ok}/{len(results)}건 성공. 요약 → {args.out_dir / 'summary.json'}")


def _process_unit(unit: MatchedUnit, args: argparse.Namespace) -> dict:
    run_dir = args.out_dir / unit.run_id / f"video{unit.video_id}"
    comparison_path = run_dir / "comparison.json"
    if comparison_path.exists():
        print("      이미 처리됨 - 스킵")
        return json.loads(comparison_path.read_text(encoding="utf-8"))

    print("      [1/3] 자산 다운로드 중... (prompt/이미지/영상)")
    assets = fetch_unit_assets(unit, run_dir / "assets", overwrite=args.overwrite_assets)

    scenario_root = run_dir / "scenario"
    video_stem = assets["video_path"].stem
    scenario_path = scenario_root / video_stem / "scenario_analysis.json"
    scenario = _load_valid_scenario(scenario_path)
    if scenario is not None:
        print("      [2/3] 기존 scenario_analysis 재사용")
    else:
        print("      [2/3] scenario_analysis 생성 중... (pipeline.cli, 수 분~수십 분 소요)")
        _run_pipeline_cli(assets["video_path"], scenario_root, args)
        scenario = require_valid_json(scenario_path, "scenario_analysis")

    print("      [3/3] 원본과 비교 중... (claude -p)")
    comparison = compare_scenario(unit, scenario, run_dir / "assets" / "images")
    comparison_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"      완료 (match_rate={comparison['overall_match_rate']})  → {comparison_path}")
    return comparison


def _load_valid_scenario(scenario_path: Path) -> dict | None:
    """기존 scenario_analysis.json 이 있고 parse_failed 가 아니면 반환, 아니면 None (재생성 필요)."""
    if not scenario_path.exists():
        return None
    try:
        data = json.loads(scenario_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return None if is_parse_failed(data) else data


def _run_pipeline_cli(video_path: Path, scenario_root: Path, args: argparse.Namespace) -> None:
    cmd = [
        sys.executable, "-m", "pipeline.cli",
        "--video_path", str(video_path),
        "--out_dir", str(scenario_root),
        "--max_cuts", str(args.max_cuts),
        "--llm_backend", args.llm_backend,
    ]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    subprocess.run(cmd, cwd=_REPO_ROOT, check=True, timeout=_PIPELINE_TIMEOUT_SEC, env=env)


def _save_summary(out_dir: Path, results: list[dict]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
