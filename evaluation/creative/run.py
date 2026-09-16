"""creative 모드 실행기 — 크리에이티브 요소 추출·적재·클리셰 리포트."""
import argparse
import json
import sys
from pathlib import Path

from utils.io_checks import require_valid_json

_ANALYSIS_FILE = "creative_element_analysis.json"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="evaluation.cli --mode creative",
                                description="크리에이티브 요소 추출 + 벡터 적재 + 클리셰 리포트")
    p.add_argument("--video_id", default=None, help="대상 영상 ID (쉼표 구분 복수 허용, extract/load_vector 에 필요)")
    p.add_argument("--data_dir", type=Path, default=Path("output/total"),
                   help="데이터 루트 (기본: output/total). 경로: <data_dir>/<video_id>/")
    p.add_argument("--extract", action="store_true", help=f"시나리오에서 요소 추출 → {_ANALYSIS_FILE}")
    p.add_argument("--industry_secondary", default=None,
                   help="[extract] 부산업 강제 지정 (예: entertainment). 배치 전체에 동일 적용. "
                        "미지정 시 category_analysis.json 의 industry_category 가 리스트면 2번째 값을 자동 사용")
    p.add_argument("--load_vector", action="store_true",
                   help=f"{_ANALYSIS_FILE} 을 profile/element 컬렉션에 upsert")
    p.add_argument("--report", action="store_true", help="세그먼트 클리셰 리포트 생성")
    p.add_argument("--db_path", type=Path, default=None,
                   help="ChromaDB 저장 경로 (기본: data/ad_production_reference/ 자동 결정)")
    # report 세그먼트 필터
    p.add_argument("--industry", default=None, help="[report] industry_category 필터 (예: beauty)")
    p.add_argument("--product_category", default=None, help="[report] product_category_norm 필터 (예: skincare)")
    p.add_argument("--product_subtype", default=None, help="[report] product_subtype 필터")
    p.add_argument("--target_gender", default=None, help="[report] target_gender 필터")
    p.add_argument("--duration_bucket", default=None, help="[report] duration_bucket 필터 (예: 15s)")
    p.add_argument("--usp", default=None, help="[report] usp_category 필터 (예: functional_tangible)")
    p.add_argument("--positioning", default=None, help="[report] positioning_category 필터")
    p.add_argument("--price_tier", default=None, help="[report] price_tier 필터 (예: luxury)")
    p.add_argument("--out", type=Path, default=None, help="[report] 리포트 JSON 저장 경로")
    return p


def _video_ids(args: argparse.Namespace) -> list[str]:
    if not args.video_id:
        print("[오류] --extract / --load_vector 에는 --video_id 가 필요하다", file=sys.stderr)
        sys.exit(1)
    return [v.strip() for v in str(args.video_id).split(",") if v.strip()]


# category_analysis.json(video_category 컬렉션)의 industry_category 어휘는 creative 의
# INDUSTRY_CATEGORIES 와 이름이 다른 경우가 있어 별칭을 흡수한다 (예: fashion→fashion_apparel).
_CATEGORY_INDUSTRY_ALIAS = {
    "fashion": "fashion_apparel",
    "healthcare": "health_medical",
}


def _industry_for(video_dir: Path) -> tuple[str, str | None]:
    """category_analysis.json 의 industry_category 로 주/부 산업을 판별한다 (없으면 other/None).

    다트비트처럼 리스트로 복수 산업이 기재된 경우 2번째 값을 부산업 후보로 쓴다
    (CLI --industry_secondary 가 있으면 그쪽이 우선한다).
    """
    from evaluation.creative.element_schema import INDUSTRY_CATEGORIES
    path = video_dir / "category_analysis.json"
    if not path.exists():
        return "other", None
    value = json.loads(path.read_text(encoding="utf-8")).get("industry_category")
    secondary = None
    if isinstance(value, list):
        secondary = value[1] if len(value) > 1 else None
        value = value[0] if value else None
    value = _CATEGORY_INDUSTRY_ALIAS.get(value, value)
    secondary = _CATEGORY_INDUSTRY_ALIAS.get(secondary, secondary)
    primary = value if value in INDUSTRY_CATEGORIES else "other"
    secondary = secondary if secondary in INDUSTRY_CATEGORIES else None
    return primary, secondary


def _run_extract(args: argparse.Namespace) -> None:
    from evaluation.creative.element_analysis import extract_elements
    for vid in _video_ids(args):
        video_dir = args.data_dir / vid
        scenario = require_valid_json(video_dir / "scenario_analysis.json", "scenario_analysis")
        industry, auto_secondary = _industry_for(video_dir)
        secondary = args.industry_secondary or auto_secondary
        label = f"{industry}+{secondary}" if secondary else industry
        print(f"  요소 추출 중 [claude] video_id={vid} (industry={label})...")
        result = extract_elements(scenario, industry, secondary)
        if "error" in result:
            print(f"  [경고] 추출 실패 (video_id={vid}): {result.get('error')}", file=sys.stderr)
        else:
            print(f"  요소 {len(result.get('elements') or [])}건 추출")
        result["_meta"] = {"video_id": vid, "llm_backend": "claude"}
        out_path = video_dir / _ANALYSIS_FILE
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  저장: {out_path}")


def _enrich_from_concept(analysis: dict, video_dir: Path) -> None:
    """usp/positioning 미기재 구버전 파일에 concept_evaluation 대표값을 보강한다."""
    profile = analysis.setdefault("profile", {})
    path = video_dir / "concept_evaluation.json"
    if profile.get("usp_category") or not path.exists():
        return
    concept = json.loads(path.read_text(encoding="utf-8"))
    for src, cat_key, sum_key in (("usp", "usp_category", "usp_summary"),
                                  ("positioning", "positioning_category", None)):
        block = concept.get(src) or {}
        if isinstance(block, str):  # 구버전 concept 스키마: 평문 서술만 존재 (category 없음)
            if sum_key:
                profile.setdefault(sum_key, block[:200])
            continue
        if cats := block.get("category"):
            profile[cat_key] = cats[0]
        if sum_key and block.get("description"):
            profile[sum_key] = block["description"][:200]


def _run_load_vector(args: argparse.Namespace) -> None:
    from db.chromadb.importers.production_reference import upsert_analysis
    for vid in _video_ids(args):
        analysis = require_valid_json(args.data_dir / vid / _ANALYSIS_FILE, "creative_element_analysis")
        if "error" in analysis:
            print(f"[오류] {_ANALYSIS_FILE} 에 에러 있음 (video_id={vid})", file=sys.stderr)
            sys.exit(1)
        _enrich_from_concept(analysis, args.data_dir / vid)
        upsert_analysis(video_id=int(vid), analysis=analysis, db_path=args.db_path)


def _run_report(args: argparse.Namespace) -> None:
    from evaluation.creative.cliche_aggregate import aggregate_elements, format_report
    from db.chromadb.importers.production_reference import (
        build_segment_where, fetch_elements, fetch_profiles,
    )
    where = build_segment_where(
        industry_category=args.industry,
        product_category_norm=args.product_category,
        product_subtype=args.product_subtype,
        target_gender=args.target_gender,
        duration_bucket=args.duration_bucket,
        usp_category=args.usp,
        positioning_category=args.positioning,
        price_tier=args.price_tier,
    )
    profiles = fetch_profiles(where=where, db_path=args.db_path)
    if not profiles:
        print("[경고] 세그먼트에 해당하는 profile 이 없다. --load_vector 로 먼저 적재하라.", file=sys.stderr)
        sys.exit(1)
    elements = fetch_elements(where=where, db_path=args.db_path)

    report = aggregate_elements(elements, profiles)
    segment_desc = ", ".join(
        f"{k}={v}" for k, v in (
            ("industry_category", args.industry),
            ("product_category_norm", args.product_category),
            ("product_subtype", args.product_subtype),
            ("target_gender", args.target_gender),
            ("duration_bucket", args.duration_bucket),
            ("usp_category", args.usp),
            ("positioning_category", args.positioning),
            ("price_tier", args.price_tier),
        ) if v
    ) or "전체"
    report["segment"] = segment_desc
    print(format_report(report, segment_desc))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n리포트 저장: {args.out}")


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    if not any([args.extract, args.load_vector, args.report]):
        print("[오류] --extract / --load_vector / --report 중 하나 이상 지정 필요", file=sys.stderr)
        sys.exit(1)

    if args.extract:
        _run_extract(args)
    if args.load_vector:
        _run_load_vector(args)
    if args.report:
        _run_report(args)
    print("완료.")


if __name__ == "__main__":
    main()
