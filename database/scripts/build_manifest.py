"""run_comparison_pipeline.py 결과 디렉토리를 스캔해 GUI 뷰어용 manifest.json 을 만든다.

<out_dir>/original/<run_id>/video<id>/comparison.json (원본, --video_source original) 과
<out_dir>/postprocessed/<run_id>/video<id>/comparison.json (후반 합성본) 을 모두 스캔해 하나의
manifest 로 합친다 — prompt·이미지 목록·영상 경로·비교 결과, 그리고 원본/후반합성 구분용
`stage` 필드("original"|"postprocessed")를 유닛마다 넣는다. 트래킹되는 뷰어 템플릿
(database/viewer/index.html)을 같은 디렉토리에 복사한다 — 이후 <out_dir> 를 정적 서버로
띄우면 바로 볼 수 있다.

사용 예:
  python scripts/build_manifest.py --out_dir ../../output
  cd ../../output && python -m http.server 8000   # http://localhost:8000 접속
"""
import argparse
import json
import re
import shutil
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_VIEWER_TEMPLATE = _REPO_ROOT / "database" / "viewer" / "index.html"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="비교 결과 디렉토리 → GUI 뷰어용 manifest.json 생성")
    p.add_argument("--out_dir", type=Path, required=True, help="run_comparison_pipeline.py 의 --out_dir 와 동일 경로")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    units = _scan_units(args.out_dir)
    manifest = {"generated_at": _now(), "unit_count": len(units), "units": units}
    (args.out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    shutil.copy(_VIEWER_TEMPLATE, args.out_dir / "index.html")
    print(f"유닛 {len(units)}건 → {args.out_dir / 'manifest.json'}")
    print(f"뷰어 복사 → {args.out_dir / 'index.html'}")
    print(f"\n실행: cd \"{args.out_dir}\" && python -m http.server 8000")
    print("접속: http://localhost:8000")


_GLOB_PATTERNS = (
    "original/*/video*/comparison.json",       # 원본 (video_source=original)
    "postprocessed/*/video*/comparison.json",  # 후반 합성본
)


def _scan_units(out_dir: Path) -> list[dict]:
    units = []
    seen_paths = set()
    for pattern in _GLOB_PATTERNS:
        for comparison_path in sorted(out_dir.glob(pattern)):
            if comparison_path in seen_paths:
                continue
            seen_paths.add(comparison_path)
            units.append(_build_unit(out_dir, comparison_path))
    units.sort(key=lambda u: u["comparison"].get("overall_match_rate", 0))
    return units


def _build_unit(out_dir: Path, comparison_path: Path) -> dict:
    unit_dir = comparison_path.parent
    rel_dir = unit_dir.relative_to(out_dir).as_posix()
    run_id = unit_dir.parent.name
    video_id = int(re.match(r"video(\d+)", unit_dir.name).group(1))

    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    stage = "original" if comparison.get("video_source") == "original" else "postprocessed"

    return {
        "run_id": run_id,
        "video_id": video_id,
        "dir": rel_dir,
        "stage": stage,
        "prompt": _read_prompt(unit_dir, video_id),
        "images": _list_images(unit_dir, rel_dir),
        "video": f"{rel_dir}/assets/videos/video{video_id}.mp4",
        "scenario": _read_scenario_meta(unit_dir, video_id),
        "comparison": comparison,
    }


def _read_prompt(unit_dir: Path, video_id: int) -> str:
    path = unit_dir / "assets" / "prompts" / f"video{video_id}_prompt.txt"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _list_images(unit_dir: Path, rel_dir: str) -> list[dict]:
    images_dir = unit_dir / "assets" / "images"
    results = []
    for p in sorted(images_dir.glob("scene*.png"), key=lambda f: _scene_no(f.name)):
        results.append({
            "scene_no": _scene_no(p.name),
            "file": f"{rel_dir}/assets/images/{p.name}",
        })
    return results


def _scene_no(fname: str) -> int:
    m = re.search(r"scene(\d+)", fname)
    return int(m.group(1)) if m else 0


def _read_scenario_meta(unit_dir: Path, video_id: int) -> dict:
    path = unit_dir / "scenario" / f"video{video_id}" / "scenario_analysis.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {
        "title": data.get("title", ""),
        "brand": data.get("brand", ""),
        "concept": data.get("concept", ""),
        "scenes_count": len(data.get("scenes", [])),
    }


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    main()
