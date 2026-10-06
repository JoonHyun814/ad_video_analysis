"""parsed 모드 실행기 — 파이프라인 산출물 종합으로 parsed_analysis 생성."""
import argparse
import json
import sys
from pathlib import Path

from utils.gemini_caller import DEFAULT_MODEL as _GEMINI_DEFAULT_MODEL
from utils.io_checks import load_optional_valid, require_valid_json

_LLM_BACKENDS = ("claude", "codex", "qwen", "gemini")
_QWEN_DEFAULT_MODEL = "unsloth/Qwen2.5-VL-7B-Instruct"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="evaluation.cli --mode parsed",
                                description="scenario/cuts/cut_analysis/scene_analysis/stt/audio 로 parsed_analysis 생성")
    p.add_argument("--video_id", required=True, help="대상 영상 ID")
    p.add_argument("--data_dir", type=Path, default=Path("output/codex"), help="데이터 루트 (기본: output/codex)")
    p.add_argument("--output_dir", type=Path, default=None, help="저장 루트. 미지정 시 --data_dir 사용")
    p.add_argument("--llm_backend", choices=_LLM_BACKENDS, default="claude", help="LLM 백엔드 (기본: claude)")
    p.add_argument("--qwen_model", default=_QWEN_DEFAULT_MODEL, help="[qwen] 베이스 모델명/경로")
    p.add_argument("--codex_model", default=None, help="[codex] 사용할 모델명")
    p.add_argument("--gemini_model", default=_GEMINI_DEFAULT_MODEL, help=f"[gemini] 사용할 모델명 (기본: {_GEMINI_DEFAULT_MODEL})")
    return p


def _load_cuts(path: Path) -> list:
    from pipeline.cuts import Cut
    data = require_valid_json(path, "cuts")
    return [Cut(**d) for d in data]


def _dispatch_parsed(scenario: dict, cuts: list, cut_analysis: list, scene_analysis: list,
                     stt_segments: list, audio_data: dict, args: argparse.Namespace) -> dict:
    kw = dict(
        scenario=scenario,
        cuts=cuts,
        cut_analysis=cut_analysis,
        scene_analysis=scene_analysis,
        stt_segments=stt_segments,
        audio_data=audio_data,
    )
    if args.llm_backend == "codex":
        from evaluation.parsed.parsed_analysis_codex import analyze_parsed_codex
        return analyze_parsed_codex(**kw)
    if args.llm_backend == "qwen":
        from pipeline import qwen_client
        if qwen_client._llm is None:
            qwen_client.init(model=args.qwen_model)
        from evaluation.parsed.parsed_analysis_qwen import analyze_parsed_qwen
        return analyze_parsed_qwen(**kw)
    if args.llm_backend == "gemini":
        from evaluation.parsed.parsed_analysis_gemini import analyze_parsed_gemini
        return analyze_parsed_gemini(model=args.gemini_model, **kw)
    from evaluation.parsed.parsed_analysis import analyze_parsed
    return analyze_parsed(**kw)


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    video_dir = args.data_dir / str(args.video_id)
    if not video_dir.exists():
        print(f"[오류] 데이터 디렉토리 없음: {video_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"[Parsed 분석] video_id={args.video_id}, backend={args.llm_backend}")
    scenario = require_valid_json(video_dir / "scenario_analysis.json", "scenario_analysis")
    cut_analysis = require_valid_json(video_dir / "cut_analysis.json", "cut_analysis")
    cuts = _load_cuts(video_dir / "cuts.json")
    scene_analysis = load_optional_valid(video_dir / "scene_analysis.json", "scene_analysis", default=[])
    stt_segments = load_optional_valid(video_dir / "stt.json", "stt", default=[])
    audio_data = load_optional_valid(video_dir / "audio_analysis.json", "audio_analysis", default={})

    parsed = _dispatch_parsed(scenario, cuts, cut_analysis, scene_analysis, stt_segments, audio_data, args)

    if "error" in parsed:
        print(f"  [경고] Parsed 분석 실패: {parsed.get('error')}")
    parsed["_meta"] = {"video_id": args.video_id, "llm_backend": args.llm_backend}

    out_root = args.output_dir if args.output_dir is not None else args.data_dir
    out_path = out_root / str(args.video_id) / "parsed_analysis.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {out_path}")
    print("완료.")


if __name__ == "__main__":
    main()
