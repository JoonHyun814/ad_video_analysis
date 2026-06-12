#!/usr/bin/env python3
"""video_id 별 분석 결과 JSON의 누락·파싱 실패를 검사해 분류한다.

--mode scenario (기본)
  Group A: scenario_analysis 만 없음      (cut + scene 존재)
  Group B: scenario_analysis + cut 없음   (scene 존재)
  Group C: scene + cut + scenario 모두 없음

--mode brief
  OK      : brief_analysis.json 존재 + 유효
  Missing : 파일 없음
  Failed  : 파일 있으나 parse_failed

--mode parsed
  OK      : parsed_analysis.json 존재 + 유효
  Missing : 파일 없음
  Failed  : 파일 있으나 parse_failed
"""

import argparse
import json
import sys
from pathlib import Path


def is_ok(path: Path) -> bool:
    """파일이 존재하고 유효한 JSON이며 parse_failed 에러가 없으면 True."""
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("error") == "parse_failed":
            return False
        if isinstance(data, list) and any(
            isinstance(item, dict) and item.get("error") == "parse_failed"
            for item in data
        ):
            return False
        return True
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False


def is_failed(path: Path) -> bool:
    """파일이 존재하지만 parse_failed 또는 JSON 오류인 경우 True."""
    if not path.exists():
        return False
    return not is_ok(path)


def _video_dirs(base_dir: Path):
    return sorted((p for p in base_dir.iterdir() if p.is_dir()), key=lambda p: p.name)


def classify_scenario(base_dir: Path):
    ok, group_a, group_b, group_c = [], [], [], []

    for video_dir in _video_dirs(base_dir):
        scene_ok    = is_ok(video_dir / "scene_analysis.json")
        cut_ok      = is_ok(video_dir / "cut_analysis.json")
        scenario_ok = is_ok(video_dir / "scenario_analysis.json")
        vid = video_dir.name

        effective_scenario_ok = scenario_ok and cut_ok

        if effective_scenario_ok:
            ok.append(vid)
        elif cut_ok and scene_ok:
            group_a.append(vid)
        elif scene_ok:
            group_b.append(vid)
        else:
            group_c.append(vid)

    return ok, group_a, group_b, group_c


def classify_single(base_dir: Path, filename: str):
    ok, missing, failed = [], [], []

    for video_dir in _video_dirs(base_dir):
        path = video_dir / filename
        vid = video_dir.name
        if is_ok(path):
            ok.append(vid)
        elif path.exists():
            failed.append(vid)
        else:
            missing.append(vid)

    return ok, missing, failed


def show(label: str, ids: list[str]) -> None:
    print(f"[{label}] ({len(ids)}개)")
    print(f"  {','.join(ids) if ids else '없음'}")
    print()


def run_scenario(base_dir: Path) -> None:
    ok, group_a, group_b, group_c = classify_scenario(base_dir)
    total = len(ok) + len(group_a) + len(group_b) + len(group_c)

    print(f"전체: {total}  /  정상: {len(ok)}  /  문제: {len(group_a)+len(group_b)+len(group_c)}")
    print()
    show("A  scenario_analysis 만 없음  (cut + scene 존재)", group_a)
    show("B  scenario_analysis + cut_analysis 없음  (scene 존재)", group_b)
    show("C  scene + cut + scenario 모두 없음", group_c)

    if not (group_a or group_b or group_c):
        print("문제 없음 — 모든 video_id 정상.")


def run_single(base_dir: Path, filename: str, label: str) -> None:
    ok, missing, failed = classify_single(base_dir, filename)
    total = len(ok) + len(missing) + len(failed)

    print(f"전체: {total}  /  정상: {len(ok)}  /  없음: {len(missing)}  /  실패: {len(failed)}")
    print()
    show("Missing  파일 없음", missing)
    show("Failed   parse_failed / JSON 오류", failed)

    if not (missing or failed):
        print(f"문제 없음 — 모든 video_id 에 {label} 정상.")


def main() -> None:
    parser = argparse.ArgumentParser(description="분석 결과 JSON 누락·파싱 실패 검사")
    parser.add_argument("base_dir", help="video_id 폴더들의 상위 디렉토리")
    parser.add_argument(
        "--mode",
        choices=["scenario", "brief", "parsed"],
        default="scenario",
        help="검사 모드 (기본: scenario)",
    )
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    if not base_dir.exists():
        print(f"ERROR: 디렉토리를 찾을 수 없습니다: {base_dir}", file=sys.stderr)
        sys.exit(1)

    if args.mode == "scenario":
        run_scenario(base_dir)
    elif args.mode == "brief":
        run_single(base_dir, "brief_analysis.json", "brief_analysis")
    elif args.mode == "parsed":
        run_single(base_dir, "parsed_analysis.json", "parsed_analysis")


if __name__ == "__main__":
    main()
