"""prompt+스토리보드 이미지+영상이 모두 있는 데이터에 대해 scenario_analysis 생성 → 원본 비교를
일괄 수행한다.

매칭 유닛(run_id, video_id)마다:
  1) 원본 프롬프트·스토리보드 이미지·영상을 내려받는다        → {run_id}/video{id}/assets/
  2) 사전 검증 — 프레임 1장 vs 스토리보드 이미지 1장으로 같은 광고인지 빠르게 확인한다
     (후반 합성이 QA 테스트 등으로 오염돼 엉뚱한 영상이 붙는 경우가 있음 — precheck.py 참고).
     오매칭으로 판정되면 10~30분 걸리는 3)을 건너뛰고 {run_id}/video{id}/skipped.json 을 남긴다.
  3) 영상으로 scenario_analysis 를 생성한다 (pipeline.cli)   → {run_id}/video{id}/scenario/
  4) scenario_analysis 를 원본과 비교해 요인별 판정을 저장한다 → {run_id}/video{id}/comparison.json

이미 처리된 유닛(comparison.json 또는 skipped.json 존재)은 건너뛴다 — 중간에 중단돼도 재실행
시 이어서 처리된다.

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
from precheck import check_video_matches_storyboard, extract_sample_frames  # noqa: E402

_LLM_BACKENDS = ("claude", "codex", "qwen", "gemini")
_PIPELINE_TIMEOUT_SEC = 3600


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="prompt+이미지+영상 매칭 데이터 scenario 생성·비교 파이프라인")
    p.add_argument("--limit", type=int, default=20, help="처리할 매칭 건수 (기본 20)")
    p.add_argument("--out_dir", type=Path, required=True, help="결과 저장 루트 (run_id 하위 폴더 생성)")
    p.add_argument(
        "--video_source", choices=("postprocessed", "original"), default="postprocessed",
        help="비교에 쓸 영상 (기본 postprocessed: 나레이션/캡션 후반 합성 완료본만, QA 테스트 제외). "
             "'original' 은 후반 합성 여부와 무관하게 AI 원본 생성 영상(videourl)을 그대로 쓴다 "
             "— 같은 videoid 라도 video<id>_original/ 하위에 별도로 저장돼 postprocessed 결과와 "
             "섞이지 않는다",
    )
    p.add_argument("--llm_backend", choices=_LLM_BACKENDS, default="claude", help="scenario_analysis 생성 LLM 백엔드")
    p.add_argument(
        "--max_cuts", type=int, default=50,
        help="scenario 생성 시 최대 컷 수 상한 (기본 50). pipeline.cli 기본값(10)보다 커야 "
             "컷수 비교가 병합으로 왜곡되지 않는다",
    )
    p.add_argument("--overwrite_assets", action="store_true", help="이미 내려받은 자산도 다시 다운로드")
    p.add_argument(
        "--skip_precheck", action="store_true",
        help="프레임 vs 스토리보드 이미지 사전 검증(오매칭 감지)을 생략하고 바로 scenario 생성으로 진행",
    )
    p.add_argument(
        "--require_verified_caption", action="store_true",
        help="(video_source=postprocessed 전용) 오매칭이 확인된 적 없는 해시 포함 캡션 파일명"
             "(`_crf23_fast_none_`)만 후보로 선택 — matching.py 참고",
    )
    return p.parse_args()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    units = fetch_matched_units(args.limit, args.video_source, args.require_verified_caption)
    print(f"매칭된 유닛 {len(units)}건 (요청 --limit {args.limit}, video_source={args.video_source})")

    results: list[dict] = []
    for i, unit in enumerate(units, 1):
        print(f"\n[{i}/{len(units)}] run={unit.run_id} video={unit.video_id} (concept {unit.concept_index})")
        try:
            results.append(_process_unit(unit, args))
        except (Exception, SystemExit) as e:
            print(f"      실패: {e}")
            results.append({"run_id": unit.run_id, "video_id": unit.video_id, "error": str(e)})
        _save_summary(args.out_dir, args.video_source, results)

    errors = sum(1 for r in results if "error" in r)
    skipped = sum(1 for r in results if r.get("skipped"))
    ok = len(results) - errors - skipped
    summary_path = args.out_dir / _summary_filename(args.video_source)
    print(f"\n완료: 성공 {ok}건 / 오매칭 스킵 {skipped}건 / 실패 {errors}건 (총 {len(results)}건). "
          f"요약 → {summary_path}")


def _process_unit(unit: MatchedUnit, args: argparse.Namespace) -> dict:
    run_dir = args.out_dir / unit.run_id / _video_dir_name(unit)
    comparison_path = run_dir / "comparison.json"
    skipped_path = run_dir / "skipped.json"
    if comparison_path.exists():
        print("      이미 처리됨 - 스킵")
        return json.loads(comparison_path.read_text(encoding="utf-8"))
    if skipped_path.exists():
        print("      이미 오매칭으로 스킵됨")
        return json.loads(skipped_path.read_text(encoding="utf-8"))

    print(f"      [1/4] 자산 다운로드 중... (prompt/이미지/영상, video_source={unit.video_source})")
    assets = fetch_unit_assets(unit, run_dir / "assets", overwrite=args.overwrite_assets)

    if not args.skip_precheck:
        print("      [2/4] 사전 검증 중... (영상 프레임 vs 스토리보드 이미지, claude -p)")
        mismatch_reason = _precheck_mismatch(unit, assets, run_dir)
        if mismatch_reason is not None:
            result = _write_skipped(unit, skipped_path, mismatch_reason)
            print(f"      스킵: 오매칭 의심 — {mismatch_reason}")
            return result

    scenario_root = run_dir / "scenario"
    video_stem = assets["video_path"].stem
    scenario_path = scenario_root / video_stem / "scenario_analysis.json"
    scenario = _load_valid_scenario(scenario_path)
    if scenario is not None:
        print("      [3/4] 기존 scenario_analysis 재사용")
    else:
        print("      [3/4] scenario_analysis 생성 중... (pipeline.cli, 수 분~수십 분 소요)")
        _run_pipeline_cli(assets["video_path"], scenario_root, args)
        scenario = require_valid_json(scenario_path, "scenario_analysis")

    print("      [4/4] 원본과 비교 중... (claude -p)")
    comparison = compare_scenario(unit, scenario, run_dir / "assets" / "images")
    comparison_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"      완료 (match_rate={comparison['overall_match_rate']})  → {comparison_path}")
    return comparison


_PRECHECK_REF_SCENE_COUNT = 3


def _precheck_mismatch(unit: MatchedUnit, assets: dict, run_dir: Path) -> str | None:
    """오매칭으로 판정되면 그 사유 문자열을, 판정 불가·정상이면 None 을 반환한다 (fail-open)."""
    images_dir = run_dir / "assets" / "images"
    video_frames = extract_sample_frames(assets["video_path"], images_dir, count=3)
    if not video_frames:
        return None

    ref_images = [
        images_dir / f"scene{s.get('no')}.png"
        for s in _sample_scenes(unit.scenes, _PRECHECK_REF_SCENE_COUNT)
    ]
    ref_images = [p for p in ref_images if p.exists()]
    if not ref_images:
        return None

    verdict = check_video_matches_storyboard(video_frames, ref_images)
    if verdict.get("same_ad") is False:
        return verdict.get("reason", "사유 없음")
    return None


def _sample_scenes(scenes: list[dict], count: int) -> list[dict]:
    """스토리보드 씬 목록에서 처음·중간·마지막 등 최대 count개를 골고루 뽑는다."""
    if len(scenes) <= count:
        return scenes
    step = (len(scenes) - 1) / (count - 1)
    return [scenes[round(i * step)] for i in range(count)]


def _write_skipped(unit: MatchedUnit, skipped_path: Path, reason: str) -> dict:
    result = {
        "run_id": unit.run_id,
        "video_id": unit.video_id,
        "storyboard_id": unit.storyboard_id,
        "concept_index": unit.concept_index,
        "video_source": unit.video_source,
        "skipped": True,
        "reason": "video_mismatch_precheck",
        "precheck_reason": reason,
    }
    skipped_path.parent.mkdir(parents=True, exist_ok=True)
    skipped_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


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


def _video_dir_name(unit: MatchedUnit) -> str:
    """postprocessed 결과와 겹치지 않도록, original 모드 결과는 video<id>_original/ 에 저장한다."""
    suffix = "_original" if unit.video_source == "original" else ""
    return f"video{unit.video_id}{suffix}"


def _summary_filename(video_source: str) -> str:
    return "summary.json" if video_source == "postprocessed" else f"summary_{video_source}.json"


def _save_summary(out_dir: Path, video_source: str, results: list[dict]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / _summary_filename(video_source)).write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
