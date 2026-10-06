"""brief 모드 실행기 — scenario_analysis 에서 brief_analysis 생성."""
import argparse
import json
import sys
from pathlib import Path

from utils.gemini_caller import DEFAULT_MODEL as _GEMINI_DEFAULT_MODEL
from utils.io_checks import require_valid_json

_LLM_BACKENDS = ("claude", "codex", "qwen", "gemini")
_QWEN_DEFAULT_MODEL = "unsloth/Qwen2.5-VL-7B-Instruct"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="evaluation.cli --mode brief", description="scenario_analysis 로 brief_analysis 생성")
    p.add_argument("--video_id", required=True, help="대상 영상 ID")
    p.add_argument("--data_dir", type=Path, default=Path("output/codex"), help="데이터 루트 (기본: output/codex)")
    p.add_argument("--output_dir", type=Path, default=None, help="저장 루트. 미지정 시 --data_dir 사용")
    p.add_argument("--llm_backend", choices=_LLM_BACKENDS, default="claude", help="LLM 백엔드 (기본: claude)")
    p.add_argument("--qwen_model", default=_QWEN_DEFAULT_MODEL, help="[qwen] 베이스 모델명/경로")
    p.add_argument("--codex_model", default=None, help="[codex] 사용할 모델명")
    p.add_argument("--gemini_model", default=_GEMINI_DEFAULT_MODEL, help=f"[gemini] 사용할 모델명 (기본: {_GEMINI_DEFAULT_MODEL})")
    return p


def _dispatch_brief(scenario: dict, args: argparse.Namespace) -> dict:
    if args.llm_backend == "codex":
        from evaluation.brief.brief_generator_codex import generate_brief_codex
        return generate_brief_codex(scenario, model=args.codex_model)
    if args.llm_backend == "qwen":
        from pipeline import qwen_client
        qwen_client.init(model=args.qwen_model)
        from evaluation.brief.brief_generator_qwen import generate_brief_qwen
        return generate_brief_qwen(scenario)
    if args.llm_backend == "gemini":
        from evaluation.brief.brief_generator_gemini import generate_brief_gemini
        return generate_brief_gemini(scenario, model=args.gemini_model)
    from evaluation.brief.brief_generator import generate_brief
    return generate_brief(scenario)


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    video_dir = args.data_dir / str(args.video_id)
    if not video_dir.exists():
        print(f"[오류] 데이터 디렉토리 없음: {video_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"[브리프 추출] video_id={args.video_id}, backend={args.llm_backend}")
    scenario = require_valid_json(video_dir / "scenario_analysis.json", "scenario_analysis")
    brief = _dispatch_brief(scenario, args)

    if "error" in brief:
        print(f"  [경고] 브리프 추출 실패: {brief.get('error')}")
    brief["_meta"] = {"video_id": args.video_id, "llm_backend": args.llm_backend}

    out_root = args.output_dir if args.output_dir is not None else args.data_dir
    out_path = out_root / str(args.video_id) / "brief_analysis.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {out_path}")
    print("완료.")


if __name__ == "__main__":
    main()
