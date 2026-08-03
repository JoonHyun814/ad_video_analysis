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
    p.add_argument("--load_vector", action="store_true",
                   help="strategy_analysis.json(evaluation/strategy/run.py 로 미리 추출 — M1·M2·M3 "
                        "역추출 결과)을 벡터 DB(ad_concept_reference)에 적재 — M3(컨셉 발산)이 "
                        "참고하는 전략 레퍼런스 컬렉션. 같은 디렉터리에 creative_element_analysis.json"
                        "이 있으면 target_gender/duration_bucket/price_tier 를, concept_evaluation.json"
                        "(구 스키마)이 있으면 카테고리 세그먼트 필터를 추가로 크로스 적재한다(둘 다 없어도 무방)")
    p.add_argument("--load_facets", action="store_true",
                   help="[레거시, generation/segment_retrieval.py 전용] concept_evaluation.json 을 "
                        "facet 컬렉션 3개(ad_target/ad_usp/ad_creative)에 적재. ad_concept_reference "
                        "와는 무관하다")
    p.add_argument("--db_path", type=Path, default=Path("output/vector_db"), help="ChromaDB 저장 경로 (기본: output/vector_db)")
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
        from evaluation.concept.concept_evaluation_codex import evaluate_concept_codex
        return evaluate_concept_codex(scenario, model=args.codex_model)
    if args.llm_backend == "qwen":
        from pipeline import qwen_client
        if qwen_client._llm is None:
            qwen_client.init(model=args.qwen_model)
        from evaluation.concept.concept_evaluation_qwen import evaluate_concept_qwen
        return evaluate_concept_qwen(scenario)
    if args.llm_backend == "gemini":
        from evaluation.concept.concept_evaluation_gemini import evaluate_concept_gemini
        return evaluate_concept_gemini(scenario, model=args.gemini_model)
    from evaluation.concept.concept_evaluation import evaluate_concept
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


def _load_concept(args: argparse.Namespace, video_dir: Path) -> dict:
    concept = require_valid_json(video_dir / "concept_evaluation.json", "concept_evaluation")
    if "error" in concept:
        print(f"[오류] concept_evaluation.json 에 에러 있음: {concept.get('error')}", file=sys.stderr)
        sys.exit(1)
    return concept


_ENRICH_KEYS = ("target_gender", "duration_bucket", "price_tier")


def _enrich_from_creative(video_dir: Path) -> dict | None:
    """같은 영상의 creative_element_analysis.json profile 에서 target_gender/duration_bucket/
    price_tier 를 뽑아 ad_concept_reference 크로스 세그먼트 필터로 쓴다(없으면 None)."""
    path = video_dir / "creative_element_analysis.json"
    if not path.exists():
        return None
    profile = (json.loads(path.read_text(encoding="utf-8")) or {}).get("profile") or {}
    enrich = {k: profile[k] for k in _ENRICH_KEYS if profile.get(k) is not None}
    return enrich or None


def _load_strategy(video_dir: Path) -> dict:
    strategy = require_valid_json(video_dir / "strategy_analysis.json", "strategy_analysis")
    for module in ("m1", "m2", "m3"):
        if error := strategy.get(module, {}).get("error"):
            print(f"[오류] strategy_analysis.json 의 {module} 추출 실패: {error}", file=sys.stderr)
            sys.exit(1)
    return strategy


def _load_concept_eval_optional(video_dir: Path) -> dict | None:
    """concept_evaluation.json(구 스키마, 있으면) — 세그먼트 필터 보조 카테고리용."""
    path = video_dir / "concept_evaluation.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return None if "error" in data else data


def _run_load_vector(args: argparse.Namespace, video_dir: Path) -> None:
    from evaluation.concept.concept_reference_store import upsert_concept_reference
    upsert_concept_reference(
        video_id=int(args.video_id),
        strategy=_load_strategy(video_dir),
        db_path=args.db_path,
        enrich=_enrich_from_creative(video_dir),
        concept_eval=_load_concept_eval_optional(video_dir),
    )


def _run_load_facets(args: argparse.Namespace, video_dir: Path) -> None:
    from evaluation.concept.facet_vector_store import upsert_facets
    upsert_facets(
        video_id=int(args.video_id),
        concept=_load_concept(args, video_dir),
        db_path=args.db_path,
    )


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    video_dir = args.data_dir / str(args.video_id)

    if not video_dir.exists():
        print(f"[오류] 데이터 디렉토리 없음: {video_dir}", file=sys.stderr)
        sys.exit(1)

    if not any([args.concept_evaluation, args.load_vector, args.load_facets]):
        print("[오류] --concept_evaluation / --load_vector / --load_facets 중 하나 이상 지정 필요", file=sys.stderr)
        sys.exit(1)

    print(f"[컨셉 평가] video_id={args.video_id}, backend={args.llm_backend}")

    if args.concept_evaluation:
        _run_concept_evaluation(args, video_dir)

    if args.load_vector:
        _run_load_vector(args, video_dir)

    if args.load_facets:
        _run_load_facets(args, video_dir)

    print("완료.")


if __name__ == "__main__":
    main()
