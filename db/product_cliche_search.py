"""제품명으로 유사 광고를 검색하고, 세그먼트 클리셰를 비튼 광고를 분석해 txt로 저장하는 CLI.

python -m db.product_cliche_search --product_name "세스코" --retrieval_criteria usp
"""
import argparse
import sys
from pathlib import Path

from db.ad_retrieval import retrieve_similar_ads
from db.cliche_twist_analysis import aggregate_twist_strategies, build_segment_report, select_notable_cliches
from db.cliche_twist_format import format_report
from db.product_research import research_product

_DEFAULT_DB = Path("output/vector_db")
_DEFAULT_OUT_DIR = Path("output/cliche_twist")

_QUERY_BUILDERS = {
    "category": lambda p: f"산업/제품 카테고리: {p['category']}",
    "usp": lambda p: f"USP: {p['usp']}",
    "target": lambda p: f"타겟 페르소나: {p['target']}",
}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="제품 리서치 + 유사광고 검색(creative vector db) + 클리셰 비틀기 분석")
    p.add_argument("--product_name", required=True, help="조사·검색할 제품/브랜드명")
    p.add_argument("--category", default=None, help="카테고리 직접 지정 (있으면 해당 항목 조사 생략)")
    p.add_argument("--usp", default=None, help="USP 직접 지정 (있으면 해당 항목 조사 생략)")
    p.add_argument("--target", default=None, help="타겟 직접 지정 (있으면 해당 항목 조사 생략)")
    p.add_argument("--retrieval_criteria", required=True, choices=("category", "usp", "target"),
                   help="유사도 검색에 사용할 축")
    p.add_argument("--n_results", type=int, default=15, help="추출할 광고 수 (기본: 15)")
    p.add_argument("--duration_bucket", default="15s", help="대상 광고 길이 버킷 (기본: 15s)")
    p.add_argument("--db_path", type=Path, default=_DEFAULT_DB, help="ChromaDB 저장 경로")
    p.add_argument("--out", type=Path, default=None,
                   help="결과 txt 저장 경로 (기본: output/cliche_twist/<제품명>_<기준>.txt)")
    return p


def _resolve_out_path(args: argparse.Namespace) -> Path:
    if args.out:
        return args.out
    safe_name = "".join(c if c.isalnum() else "_" for c in args.product_name)
    return _DEFAULT_OUT_DIR / f"{safe_name}_{args.retrieval_criteria}.txt"


def _step_research(args: argparse.Namespace) -> dict:
    print(f"[1/3] '{args.product_name}' 마케팅 프로필 조사 중 (웹검색)...")
    profile = research_product(args.product_name, args.category, args.usp, args.target)
    if "error" in profile:
        print(f"[오류] 프로필 조사 실패: {profile.get('error')}", file=sys.stderr)
        sys.exit(1)
    return profile


def _step_retrieve(args: argparse.Namespace, profile: dict) -> list[dict]:
    print(f"[2/3] '{args.retrieval_criteria}' 기준 유사 광고 검색 중 (creative vector db)...")
    query_text = _QUERY_BUILDERS[args.retrieval_criteria](profile)
    ads = retrieve_similar_ads(query_text, duration_bucket=args.duration_bucket,
                                n_results=args.n_results, db_path=args.db_path)
    if not ads:
        print("[오류] creative vector db 에 조건에 맞는 광고가 없다 (먼저 --load_vector 로 적재 필요).",
              file=sys.stderr)
        sys.exit(1)
    print(f"  {len(ads)}편 추출됨: {[a['video_id'] for a in ads]}")
    return ads


def _step_analyze(ads: list[dict], db_path: Path) -> tuple[dict, list[dict], int, list[dict]]:
    print("[3/3] 클리셰 집계 중...")
    video_ids = [a["video_id"] for a in ads]
    report = build_segment_report(video_ids, db_path)
    notable, total_candidates = select_notable_cliches(report)
    return report, notable, total_candidates, aggregate_twist_strategies(report)


def main() -> None:
    args = _build_parser().parse_args()
    profile = _step_research(args)
    ads = _step_retrieve(args, profile)
    report, notable, total_candidates, strategies = _step_analyze(ads, args.db_path)

    out_path = _resolve_out_path(args)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = format_report(args.product_name, args.retrieval_criteria, profile,
                          report, notable, total_candidates, strategies)
    out_path.write_text(text, encoding="utf-8")
    print(f"완료: {out_path}")


if __name__ == "__main__":
    main()
