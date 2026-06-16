"""카테고리 분석 및 벡터 DB 적재 CLI."""
import argparse
import json
import sys
from pathlib import Path

from utils.gemini_caller import DEFAULT_MODEL as _GEMINI_DEFAULT

_LLM_BACKENDS = ("claude", "codex", "gemini")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="카테고리 분석 및 벡터 DB 적재")
    p.add_argument("--video_id", required=True, type=int, help="분석할 영상 ID")
    p.add_argument("--data_dir", type=Path, default=Path("output/product_plan/claude"),
                   help="데이터 루트 (기본: output/product_plan/claude). 경로: <data_dir>/<video_id>/")
    p.add_argument("--category_analysis", action="store_true", help="시나리오에서 카테고리 메타데이터 추출")
    p.add_argument("--load_vector", action="store_true", help="category_analysis.json 을 벡터 DB에 적재")
    p.add_argument("--db_path", type=Path, default=Path("output/vector_db"), help="ChromaDB 저장 경로 (기본: output/vector_db)")
    p.add_argument("--collection", default="video_category", help="ChromaDB 컬렉션명 (기본: video_category)")
    p.add_argument("--llm_backend", choices=_LLM_BACKENDS, default="claude", help="LLM 백엔드 (기본: claude)")
    p.add_argument("--codex_model", default=None, help="[codex] 모델명")
    p.add_argument("--gemini_model", default=_GEMINI_DEFAULT, help=f"[gemini] 모델명 (기본: {_GEMINI_DEFAULT})")
    return p


def _load_json(path: Path, label: str) -> dict:
    if not path.exists():
        print(f"[오류] {label} 없음: {path}", file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {path}")


def _run_category_analysis(args: argparse.Namespace, video_dir: Path) -> dict:
    scenario = _load_json(video_dir / "scenario_analysis.json", "scenario_analysis")
    brief_path = video_dir / "brief_analysis.json"
    brief = json.loads(brief_path.read_text(encoding="utf-8")) if brief_path.exists() else None

    print(f"  카테고리 분석 중 [{args.llm_backend}]...")
    result = _dispatch_analysis(scenario, brief, args)

    if "error" in result:
        print(f"  [경고] 카테고리 분석 실패: {result.get('error')}", file=sys.stderr)
    result["_meta"] = {"video_id": args.video_id, "llm_backend": args.llm_backend}
    _save_json(video_dir / "category_analysis.json", result)
    return result


def _run_load_vector(args: argparse.Namespace, video_dir: Path) -> None:
    category = _load_json(video_dir / "category_analysis.json", "category_analysis")
    if "error" in category:
        print(f"[오류] category_analysis.json 에 에러 있음: {category.get('error')}", file=sys.stderr)
        sys.exit(1)

    from evaluation.vector_store import upsert_video
    upsert_video(
        video_id=args.video_id,
        category=category,
        db_path=args.db_path,
        collection_name=args.collection,
    )


def _dispatch_analysis(scenario: dict, brief: dict | None, args: argparse.Namespace) -> dict:
    if args.llm_backend == "codex":
        from evaluation.category_analysis_codex import analyze_category_codex
        return analyze_category_codex(scenario, brief, model=args.codex_model)
    if args.llm_backend == "gemini":
        from evaluation.category_analysis_gemini import analyze_category_gemini
        return analyze_category_gemini(scenario, brief, model=args.gemini_model)
    from evaluation.category_analysis import analyze_category
    return analyze_category(scenario, brief)


def main() -> None:
    args = _build_parser().parse_args()
    video_dir = args.data_dir / str(args.video_id)

    if not video_dir.exists():
        print(f"[오류] 디렉토리 없음: {video_dir}", file=sys.stderr)
        sys.exit(1)

    if not args.category_analysis and not args.load_vector:
        print("[오류] --category_analysis / --load_vector 중 하나 이상 지정 필요", file=sys.stderr)
        sys.exit(1)

    print(f"[카테고리 분석] video_id={args.video_id}, backend={args.llm_backend}")

    if args.category_analysis:
        _run_category_analysis(args, video_dir)

    if args.load_vector:
        _run_load_vector(args, video_dir)

    print("완료.")


if __name__ == "__main__":
    main()
