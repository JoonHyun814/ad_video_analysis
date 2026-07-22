"""클리셰 인지 광고 생성 파이프라인 CLI (G1~G6)."""
import argparse
import sys
from pathlib import Path

from evaluation.concept.facet_vector_store import GENRE_CHOICES
from generation.pipeline import STAGES, run_pipeline, run_single_stage, save_json
from utils.gemini_caller import DEFAULT_MODEL as _GEMINI_DEFAULT_MODEL
from utils.io_checks import is_parse_failed, require_valid_json

_LLM_BACKENDS = ("claude", "codex", "gemini")


def _add_advertiser_args(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("광고주 지정값 (미입력 시 G1 이 브리프에서 추론)")
    g.add_argument("--genre", default="",
                   help=f"광고 장르 — 자유 텍스트 또는 enum({'|'.join(GENRE_CHOICES)})")
    g.add_argument("--target_persona", default="", help="타겟 소비자 서술")
    g.add_argument("--usp", default="", help="차별화 포인트")
    g.add_argument("--positioning", default="", help="브랜드/제품 포지셔닝")
    g.add_argument("--brand_position", default="", choices=("", "leader", "challenger", "new_entrant"),
                   help="시장 지위 — 클리셰 follow/avoid 판단에 사용")
    g.add_argument("--target_age", default="", help="[브리프] 타겟 연령대")
    g.add_argument("--slogan", default="", help="[브리프] 슬로건")
    g.add_argument("--ingredients", nargs="*", default=None, help="[브리프] 핵심 성분 목록")
    g.add_argument("--functions", nargs="*", default=None, help="[브리프] 핵심 기능 목록")


def _add_vector_args(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("세그먼트/클리셰 분석 (G2·G5)")
    g.add_argument("--vector_db_path", type=Path, default=Path("output/vector_db"),
                   help="ChromaDB 저장 경로 (기본: output/vector_db)")
    g.add_argument("--min_segment", type=int, default=15,
                   help="[G2] 세그먼트 최소 표본 수 — 미달 시 필터 계층 완화 (기본: 15)")
    g.add_argument("--segment_cap", type=int, default=60,
                   help="[G2] 세그먼트 최대 멤버 수 (기본: 60)")
    g.add_argument("--code_share", type=float, default=0.75,
                   help="[G2] 이 점유율 이상이면 category_code 로 분류 (기본: 0.75)")
    g.add_argument("--cliche_share", type=float, default=0.40,
                   help="[G2] 이 점유율 이상이면 creative_cliche 로 분류 (기본: 0.40)")
    g.add_argument("--cluster_seed", type=int, default=42, help="[G2] K-Means 시드 (기본: 42)")
    g.add_argument("--avoid_distance", type=float, default=0.35,
                   help="[G5] avoid/subvert 클러스터와의 최소 cosine distance (기본: 0.35)")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="클리셰 인지 광고 생성 파이프라인 (G1~G6)")
    p.add_argument("--brand", required=True, help="브랜드명")
    p.add_argument("--product", required=True, help="제품명")
    p.add_argument("--brief", action="store_true", help="웹 검색으로 브리프 생성")
    p.add_argument("--pipeline", action="store_true", help="G1→G6 전체 파이프라인 실행")
    p.add_argument("--stage", choices=STAGES, help="특정 단계만 실행 (이전 단계 출력 파일 필요)")
    _add_advertiser_args(p)
    _add_vector_args(p)
    p.add_argument("--duration", type=float, default=30.0, help="[G6] 영상 길이(초) (기본: 30)")
    p.add_argument("--concept_id", default=None, help="[G6] 시나리오로 확장할 컨셉 ID (기본: G5 통과 첫 컨셉)")
    p.add_argument("--llm_backend", choices=_LLM_BACKENDS, default="claude", help="LLM 백엔드 (기본: claude)")
    p.add_argument("--codex_model", default=None, help="[codex] 사용할 모델명")
    p.add_argument("--gemini_model", default=_GEMINI_DEFAULT_MODEL,
                   help=f"[gemini] 모델명 (기본: {_GEMINI_DEFAULT_MODEL})")
    p.add_argument("--output_dir", type=Path, default=Path("output/generation"),
                   help="저장 디렉토리 (기본: output/generation)")
    return p


def _build_seed_brief(args: argparse.Namespace) -> dict:
    """CLI 입력값으로 웹 검색 없이 최소 브리프를 구성한다."""
    brief: dict = {"brand": args.brand, "product": args.product}
    for key in ("usp", "target_age", "target_persona", "positioning", "slogan"):
        if val := getattr(args, key, ""):
            brief[key] = val
    if args.ingredients:
        brief["ingredients"] = args.ingredients
    if args.functions:
        brief["functions"] = args.functions
    return brief


def _run_brief(args: argparse.Namespace) -> dict:
    from generation.brief_generator import generate_brief_from_web
    brief = generate_brief_from_web(
        args.brand, args.product,
        usp=args.usp, target_age=args.target_age, target_persona=args.target_persona,
        positioning=args.positioning, slogan=args.slogan,
        ingredients=args.ingredients, functions=args.functions,
        llm_backend=args.llm_backend, codex_model=args.codex_model, gemini_model=args.gemini_model,
    )
    if "error" in brief:
        print(f"  [경고] 브리프 생성 실패: {brief.get('error')}", file=sys.stderr)
    save_json(args.output_dir / f"{args.brand}_{args.product}.json", brief)
    return brief


def _resolve_brief(args: argparse.Namespace) -> dict:
    """--brief 면 웹 검색 브리프, 기존 브리프 파일이 있으면 재사용, 없으면 seed 브리프."""
    brief_path = args.output_dir / f"{args.brand}_{args.product}.json"
    if args.brief:
        brief = _run_brief(args)
        if is_parse_failed(brief):
            raise SystemExit("[오류] 브리프 결과에 parse_failed 항목 있음. 재실행 필요.")
        return brief
    if brief_path.exists():
        print(f"  기존 브리프 재사용: {brief_path}")
        return require_valid_json(brief_path, "brief")
    return _build_seed_brief(args)


def main() -> None:
    args = _build_parser().parse_args()
    if not any([args.brief, args.pipeline, args.stage]):
        print("[오류] --brief / --pipeline / --stage 중 하나 이상 지정 필요", file=sys.stderr)
        sys.exit(1)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[생성 파이프라인] brand={args.brand}, product={args.product}, backend={args.llm_backend}")

    brief = _resolve_brief(args)
    if args.pipeline:
        run_pipeline(args, brief)
    elif args.stage:
        run_single_stage(args, brief)
    print("완료.")


if __name__ == "__main__":
    main()
