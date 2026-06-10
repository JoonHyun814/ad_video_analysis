"""광고 콘티 평가 파이프라인 CLI."""
import argparse
import json
import sys
from pathlib import Path

_LLM_BACKENDS = ("claude", "codex", "qwen", "gemini")
_QWEN_DEFAULT_MODEL = "unsloth/Qwen2.5-VL-7B-Instruct"

from utils.gemini_caller import DEFAULT_MODEL as _GEMINI_DEFAULT_MODEL


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="광고 콘티 평가 파이프라인")
    p.add_argument("--video_id", required=True, help="평가할 영상 ID")
    p.add_argument("--data_dir", type=Path, default=Path("output/codex"), help="데이터 루트 (기본: output/codex)")
    p.add_argument("--output_dir", type=Path, default=None, help="[--brief / --parsed_analysis] 저장 루트. 미지정 시 --data_dir 사용. 저장 경로: <output_dir>/<video_id>/{brief_analysis|parsed_analysis}.json")
    p.add_argument("--brief", action="store_true", help="scenario_analysis 로 brief_analysis 생성")
    p.add_argument("--parsed_analysis", action="store_true", help="scenario/cuts/cut_analysis/scene_analysis/stt/audio 로 parsed_analysis 생성")
    p.add_argument("--scenario_evaluation", action="store_true", help="brief_analysis 와 scenario_analysis 비교 평가")
    p.add_argument("--llm_backend", choices=_LLM_BACKENDS, default="claude", help="LLM 백엔드 (기본: claude)")
    p.add_argument("--qwen_model", default=_QWEN_DEFAULT_MODEL, help="[qwen] 베이스 모델명/경로")
    p.add_argument("--codex_model", default=None, help="[codex] 사용할 모델명")
    p.add_argument("--gemini_model", default=_GEMINI_DEFAULT_MODEL, help=f"[gemini] 사용할 모델명 (기본: {_GEMINI_DEFAULT_MODEL})")
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

    out_root = args.output_dir if args.output_dir is not None else args.data_dir
    out_path = out_root / str(args.video_id) / "brief_analysis.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _save_json(out_path, brief)


def _run_parsed_analysis(args: argparse.Namespace, video_dir: Path) -> None:
    scenario_path = video_dir / "scenario_analysis.json"
    if not scenario_path.exists():
        raise SystemExit(f"[오류] scenario_analysis.json 없음: {scenario_path}\n--data_dir 안에 scenario_analysis 단계까지 완료된 결과가 필요합니다.")
    scenario = _load_json(scenario_path, "scenario_analysis")
    cuts = _load_cuts(video_dir / "cuts.json")
    cut_analysis = _load_optional_list(video_dir / "cut_analysis.json")
    scene_analysis = _load_optional_list(video_dir / "scene_analysis.json")
    stt_segments = _load_optional_list(video_dir / "stt.json")
    audio_data = _load_optional_dict(video_dir / "audio_analysis.json")

    print(f"  Parsed 분석 중 [{args.llm_backend}]...")
    parsed = _dispatch_parsed(scenario, cuts, cut_analysis, scene_analysis, stt_segments, audio_data, args)

    if "error" in parsed:
        print(f"  [경고] Parsed 분석 실패: {parsed.get('error')}")
    parsed["_meta"] = {"video_id": args.video_id, "llm_backend": args.llm_backend}

    out_root = args.output_dir if args.output_dir is not None else args.data_dir
    out_path = out_root / str(args.video_id) / "parsed_analysis.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _save_json(out_path, parsed)


def _load_cuts(path: Path) -> list:
    from pipeline.cuts import Cut
    if not path.exists():
        print(f"[오류] cuts.json 파일 없음: {path}")
        sys.exit(1)
    return [Cut(**d) for d in json.loads(path.read_text(encoding="utf-8"))]


def _load_optional_list(path: Path) -> list:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _load_optional_dict(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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
    if args.llm_backend == "gemini":
        from evaluation.brief_generator_gemini import generate_brief_gemini
        return generate_brief_gemini(scenario, model=args.gemini_model)
    from evaluation.brief_generator import generate_brief
    return generate_brief(scenario)


def _dispatch_parsed(
    scenario: dict,
    cuts: list,
    cut_analysis: list,
    scene_analysis: list,
    stt_segments: list,
    audio_data: dict,
    args: argparse.Namespace,
) -> dict:
    kw = dict(
        scenario=scenario,
        cuts=cuts,
        cut_analysis=cut_analysis,
        scene_analysis=scene_analysis,
        stt_segments=stt_segments,
        audio_data=audio_data,
    )
    if args.llm_backend == "codex":
        from evaluation.parsed_analysis_codex import analyze_parsed_codex
        return analyze_parsed_codex(**kw)
    if args.llm_backend == "qwen":
        from pipeline import qwen_client
        if qwen_client._llm is None:
            qwen_client.init(model=args.qwen_model)
        from evaluation.parsed_analysis_qwen import analyze_parsed_qwen
        return analyze_parsed_qwen(**kw)
    if args.llm_backend == "gemini":
        from evaluation.parsed_analysis_gemini import analyze_parsed_gemini
        return analyze_parsed_gemini(model=args.gemini_model, **kw)
    from evaluation.parsed_analysis import analyze_parsed
    return analyze_parsed(**kw)


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
    if args.llm_backend == "gemini":
        from evaluation.evaluator_gemini import evaluate_scenario_gemini
        return evaluate_scenario_gemini(brief, scenario, model=args.gemini_model)
    from evaluation.evaluator import evaluate_scenario
    return evaluate_scenario(brief, scenario)


def main() -> None:
    args = _build_parser().parse_args()
    video_dir = args.data_dir / str(args.video_id)

    if not video_dir.exists():
        print(f"[오류] 데이터 디렉토리 없음: {video_dir}")
        sys.exit(1)

    if not args.brief and not args.parsed_analysis and not args.scenario_evaluation:
        print("[오류] --brief / --parsed_analysis / --scenario_evaluation 중 하나 이상 지정 필요")
        sys.exit(1)

    print(f"[평가 파이프라인] video_id={args.video_id}, backend={args.llm_backend}")

    if args.brief:
        _run_brief(args, video_dir)

    if args.parsed_analysis:
        _run_parsed_analysis(args, video_dir)

    if args.scenario_evaluation:
        _run_evaluation(args, video_dir)

    print("완료.")


if __name__ == "__main__":
    main()
