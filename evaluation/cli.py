"""광고 콘티 평가 파이프라인 CLI."""
import argparse
import json
import sys
from pathlib import Path

_LLM_BACKENDS = ("claude", "codex", "qwen")
_QWEN_DEFAULT_MODEL = "unsloth/Qwen2.5-VL-7B-Instruct"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="광고 콘티 평가 파이프라인")
    p.add_argument("--video_id", required=True, help="평가할 영상 ID")
    p.add_argument("--data_dir", type=Path, default=Path("output/codex"), help="데이터 루트 (기본: output/codex)")
    p.add_argument("--brief", action="store_true", help="scenario_analysis 로 brief_analysis 생성")
    p.add_argument("--scenario_evaluation", action="store_true", help="brief_analysis 와 scenario_analysis 비교 평가")
    p.add_argument("--llm_backend", choices=_LLM_BACKENDS, default="claude", help="LLM 백엔드 (기본: claude)")
    p.add_argument("--qwen_model", default=_QWEN_DEFAULT_MODEL, help="[qwen] 베이스 모델명/경로")
    p.add_argument("--codex_model", default=None, help="[codex] 사용할 모델명")
    return p


def _load_json(path: Path, label: str) -> dict:
    if not path.exists():
        print(f"[오류] {label} 파일 없음: {path}")
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {path}")


def _run_brief(args: argparse.Namespace, video_dir: Path) -> None:
    scenario_path = video_dir / "scenario_analysis.json"
    scenario = _load_json(scenario_path, "scenario_analysis")

    print(f"  브리프 추출 중 [{args.llm_backend}]...")
    brief = _dispatch_brief(scenario, args)

    if "error" in brief:
        print(f"  [경고] 브리프 추출 실패: {brief.get('error')}")
    brief["_meta"] = {"video_id": args.video_id, "llm_backend": args.llm_backend}
    _save_json(video_dir / "brief_analysis.json", brief)


def _run_evaluation(args: argparse.Namespace, video_dir: Path) -> None:
    scenario = _load_json(video_dir / "scenario_analysis.json", "scenario_analysis")
    brief = _load_json(video_dir / "brief_analysis.json", "brief_analysis")

    print(f"  시나리오 평가 중 [{args.llm_backend}]...")
    result = _dispatch_eval(brief, scenario, args)

    if "error" in result:
        print(f"  [경고] 평가 실패: {result.get('error')}")
    else:
        print(f"  전체 점수: {result.get('overall_score', 'N/A')}")
        for cat, data in result.get("categories", {}).items():
            print(f"    {cat}: {data.get('score', 'N/A')}")
    result["_meta"] = {"video_id": args.video_id, "llm_backend": args.llm_backend}
    _save_json(video_dir / "evaluation.json", result)


def _dispatch_brief(scenario: dict, args: argparse.Namespace) -> dict:
    if args.llm_backend == "codex":
        from evaluation.brief_generator_codex import generate_brief_codex
        return generate_brief_codex(scenario, model=args.codex_model)
    if args.llm_backend == "qwen":
        from pipeline import qwen_client
        qwen_client.init(model=args.qwen_model)
        from evaluation.brief_generator_qwen import generate_brief_qwen
        return generate_brief_qwen(scenario)
    from evaluation.brief_generator import generate_brief
    return generate_brief(scenario)


def _dispatch_eval(brief: dict, scenario: dict, args: argparse.Namespace) -> dict:
    if args.llm_backend == "codex":
        from evaluation.evaluator_codex import evaluate_scenario_codex
        return evaluate_scenario_codex(brief, scenario, model=args.codex_model)
    if args.llm_backend == "qwen":
        from pipeline import qwen_client
        if qwen_client._llm is None:
            qwen_client.init(model=args.qwen_model)
        from evaluation.evaluator_qwen import evaluate_scenario_qwen
        return evaluate_scenario_qwen(brief, scenario)
    from evaluation.evaluator import evaluate_scenario
    return evaluate_scenario(brief, scenario)


def main() -> None:
    args = _build_parser().parse_args()
    video_dir = args.data_dir / str(args.video_id)

    if not video_dir.exists():
        print(f"[오류] 데이터 디렉토리 없음: {video_dir}")
        sys.exit(1)

    if not args.brief and not args.scenario_evaluation:
        print("[오류] --brief 또는 --scenario_evaluation 중 하나 이상 지정 필요")
        sys.exit(1)

    print(f"[평가 파이프라인] video_id={args.video_id}, backend={args.llm_backend}")

    if args.brief:
        _run_brief(args, video_dir)

    if args.scenario_evaluation:
        _run_evaluation(args, video_dir)

    print("완료.")


if __name__ == "__main__":
    main()
