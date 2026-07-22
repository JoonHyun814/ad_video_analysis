"""scenario_eval 모드 실행기 — 시나리오 평가 (brief 존재 시 비교 포함)."""
import argparse
import json
import sys
from pathlib import Path

from utils.gemini_caller import DEFAULT_MODEL as _GEMINI_DEFAULT_MODEL
from utils.io_checks import require_valid_json

_LLM_BACKENDS = ("claude", "codex", "qwen", "gemini")
_QWEN_DEFAULT_MODEL = "unsloth/Qwen2.5-VL-7B-Instruct"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="evaluation.cli --mode scenario_eval",
                                description="시나리오 평가 — brief_analysis.json 존재 시 브리프 비교 포함")
    p.add_argument("--video_id", required=True, help="대상 영상 ID")
    p.add_argument("--data_dir", type=Path, default=Path("output/codex"), help="데이터 루트 (기본: output/codex)")
    p.add_argument("--llm_backend", choices=_LLM_BACKENDS, default="claude", help="LLM 백엔드 (기본: claude)")
    p.add_argument("--qwen_model", default=_QWEN_DEFAULT_MODEL, help="[qwen] 베이스 모델명/경로")
    p.add_argument("--codex_model", default=None, help="[codex] 사용할 모델명")
    p.add_argument("--gemini_model", default=_GEMINI_DEFAULT_MODEL, help=f"[gemini] 사용할 모델명 (기본: {_GEMINI_DEFAULT_MODEL})")
    return p


def _dispatch_eval(brief: dict, scenario: dict, args: argparse.Namespace) -> dict:
    if args.llm_backend == "codex":
        from evaluation.scenario_eval.evaluator_codex import evaluate_scenario_codex
        return evaluate_scenario_codex(brief, scenario, model=args.codex_model)
    if args.llm_backend == "qwen":
        from pipeline import qwen_client
        if qwen_client._llm is None:
            qwen_client.init(model=args.qwen_model)
        from evaluation.scenario_eval.evaluator_qwen import evaluate_scenario_qwen
        return evaluate_scenario_qwen(brief, scenario)
    if args.llm_backend == "gemini":
        from evaluation.scenario_eval.evaluator_gemini import evaluate_scenario_gemini
        return evaluate_scenario_gemini(brief, scenario, model=args.gemini_model)
    from evaluation.scenario_eval.evaluator import evaluate_scenario
    return evaluate_scenario(brief, scenario)


def _dispatch_eval_no_brief(scenario: dict, args: argparse.Namespace) -> dict:
    if args.llm_backend == "codex":
        from evaluation.scenario_eval.evaluator_codex import evaluate_scenario_no_brief_codex
        return evaluate_scenario_no_brief_codex(scenario, model=args.codex_model)
    if args.llm_backend == "qwen":
        from pipeline import qwen_client
        if qwen_client._llm is None:
            qwen_client.init(model=args.qwen_model)
        from evaluation.scenario_eval.evaluator_qwen import evaluate_scenario_no_brief_qwen
        return evaluate_scenario_no_brief_qwen(scenario)
    if args.llm_backend == "gemini":
        from evaluation.scenario_eval.evaluator_gemini import evaluate_scenario_no_brief_gemini
        return evaluate_scenario_no_brief_gemini(scenario, model=args.gemini_model)
    from evaluation.scenario_eval.evaluator import evaluate_scenario_no_brief
    return evaluate_scenario_no_brief(scenario)


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    video_dir = args.data_dir / str(args.video_id)
    if not video_dir.exists():
        print(f"[오류] 데이터 디렉토리 없음: {video_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"[시나리오 평가] video_id={args.video_id}, backend={args.llm_backend}")
    scenario = require_valid_json(video_dir / "scenario_analysis.json", "scenario_analysis")
    brief_path = video_dir / "brief_analysis.json"

    if brief_path.exists():
        brief = require_valid_json(brief_path, "brief_analysis")
        print(f"  시나리오 평가 중 [브리프 포함 / {args.llm_backend}]...")
        result = _dispatch_eval(brief, scenario, args)
    else:
        print(f"  시나리오 평가 중 [브리프 없음 — brief_fidelity 항목 제외 / {args.llm_backend}]...")
        result = _dispatch_eval_no_brief(scenario, args)

    if "error" in result:
        print(f"  [경고] 평가 실패: {result.get('error')}")
    else:
        print(f"  전체 점수: {result.get('overall_score', 'N/A')}")
        for cat, data in result.get("categories", {}).items():
            print(f"    {cat}: {data.get('score', 'N/A')}")

    result["_meta"] = {"video_id": args.video_id, "llm_backend": args.llm_backend, "has_brief": brief_path.exists()}
    out_path = video_dir / "evaluation.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {out_path}")
    print("완료.")


if __name__ == "__main__":
    main()
