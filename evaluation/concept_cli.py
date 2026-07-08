"""광고 컨셉 추출 CLI."""
import argparse
import json
import sys
from pathlib import Path

from utils.gemini_caller import DEFAULT_MODEL as _GEMINI_DEFAULT
from utils.io_checks import require_valid_json

_LLM_BACKENDS = ("claude", "codex", "qwen", "gemini")
_QWEN_DEFAULT_MODEL = "unsloth/Qwen2.5-VL-7B-Instruct"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="광고 컨셉 추출 + 벡터 DB 적재")
    p.add_argument("--video_id", required=True, help="평가할 영상 ID")
    p.add_argument("--data_dir", type=Path, default=Path("output/codex"),
                   help="데이터 루트 (기본: output/codex). 경로: <data_dir>/<video_id>/")
    p.add_argument("--concept_evaluation", action="store_true", help="컨셉 추출 실행")
    p.add_argument("--load_vector", action="store_true", help="concept_evaluation.json 을 벡터 DB(video_concept)에 적재")
    p.add_argument("--db_path", type=Path, default=Path("output/vector_db"), help="ChromaDB 저장 경로 (기본: output/vector_db)")
    p.add_argument("--collection", default="video_concept", help="ChromaDB 컬렉션명 (기본: video_concept)")
    p.add_argument("--llm_backend", choices=_LLM_BACKENDS, default="claude", help="LLM 백엔드 (기본: claude)")
    p.add_argument("--qwen_model", default=_QWEN_DEFAULT_MODEL, help="[qwen] 베이스 모델명/경로")
    p.add_argument("--codex_model", default=None, help="[codex] 사용할 모델명")
    p.add_argument("--gemini_model", default=_GEMINI_DEFAULT, help=f"[gemini] 사용할 모델명 (기본: {_GEMINI_DEFAULT})")
    return p


def _save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {path}")


def _dispatch(scenario: dict, args: argparse.Namespace) -> dict:
    if args.llm_backend == "codex":
        from evaluation.concept_evaluation_codex import evaluate_concept_codex
        return evaluate_concept_codex(scenario, model=args.codex_model)
    if args.llm_backend == "qwen":
        from pipeline import qwen_client
        if qwen_client._llm is None:
            qwen_client.init(model=args.qwen_model)
        from evaluation.concept_evaluation_qwen import evaluate_concept_qwen
        return evaluate_concept_qwen(scenario)
    if args.llm_backend == "gemini":
        from evaluation.concept_evaluation_gemini import evaluate_concept_gemini
        return evaluate_concept_gemini(scenario, model=args.gemini_model)
    from evaluation.concept_evaluation import evaluate_concept
    return evaluate_concept(scenario)


def _run_concept_evaluation(args: argparse.Namespace, video_dir: Path) -> None:
    scenario = require_valid_json(video_dir / "scenario_analysis.json", "scenario_analysis")

    print(f"  컨셉 평가 중 [{args.llm_backend}]...")
    result = _dispatch(scenario, args)

    if "error" in result:
        print(f"  [경고] 컨셉 평가 실패: {result.get('error')}", file=sys.stderr)
    else:
        print(f"  제품 카테고리: {result.get('product_category', 'N/A')}")

    result["_meta"] = {"video_id": args.video_id, "llm_backend": args.llm_backend}
    _save_json(video_dir / "concept_evaluation.json", result)


def _run_load_vector(args: argparse.Namespace, video_dir: Path) -> None:
    concept = require_valid_json(video_dir / "concept_evaluation.json", "concept_evaluation")
    if "error" in concept:
        print(f"[오류] concept_evaluation.json 에 에러 있음: {concept.get('error')}", file=sys.stderr)
        sys.exit(1)

    from evaluation.concept_vector_store import upsert_concept
    upsert_concept(
        video_id=int(args.video_id),
        concept=concept,
        db_path=args.db_path,
        collection_name=args.collection,
    )


def main() -> None:
    args = _build_parser().parse_args()
    video_dir = args.data_dir / str(args.video_id)

    if not video_dir.exists():
        print(f"[오류] 데이터 디렉토리 없음: {video_dir}", file=sys.stderr)
        sys.exit(1)

    if not args.concept_evaluation and not args.load_vector:
        print("[오류] --concept_evaluation / --load_vector 중 하나 이상 지정 필요", file=sys.stderr)
        sys.exit(1)

    print(f"[컨셉 평가] video_id={args.video_id}, backend={args.llm_backend}")

    if args.concept_evaluation:
        _run_concept_evaluation(args, video_dir)

    if args.load_vector:
        _run_load_vector(args, video_dir)

    print("완료.")


if __name__ == "__main__":
    main()
