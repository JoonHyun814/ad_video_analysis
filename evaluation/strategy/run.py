"""M1·M2·M3 전략 스키마 역추출 CLI."""
import argparse
import json
import sys
from pathlib import Path

from utils.gemini_caller import DEFAULT_MODEL as _GEMINI_DEFAULT
from utils.io_checks import require_valid_json

from evaluation.strategy.strategy_extraction import extract_strategy

_LLM_BACKENDS = ("claude", "codex", "gemini")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="scenario_analysis 에서 M1·M2·M3 전략 스키마 역추출")
    p.add_argument("--video_id", required=True, help="분석할 영상 ID")
    p.add_argument("--data_dir", type=Path, default=Path("output/codex"),
                   help="데이터 루트 (기본: output/codex). 경로: <data_dir>/<video_id>/")
    p.add_argument("--llm_backend", choices=_LLM_BACKENDS, default="claude", help="LLM 백엔드 (기본: claude)")
    p.add_argument("--codex_model", default=None, help="[codex] 사용할 모델명")
    p.add_argument("--gemini_model", default=_GEMINI_DEFAULT, help=f"[gemini] 사용할 모델명 (기본: {_GEMINI_DEFAULT})")
    p.add_argument("--timeout", type=int, default=600, help="모듈별 LLM 호출 타임아웃 초 (기본: 600)")
    return p


def _save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {path}")


def _warn_failures(result: dict) -> None:
    for module in ("m1", "m2", "m3"):
        error = result.get(module, {}).get("error")
        if error:
            print(f"  [경고] {module} 추출 실패: {error}", file=sys.stderr)


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    video_dir = args.data_dir / str(args.video_id)

    if not video_dir.exists():
        print(f"[오류] 데이터 디렉토리 없음: {video_dir}", file=sys.stderr)
        sys.exit(1)

    scenario = require_valid_json(video_dir / "scenario_analysis.json", "scenario_analysis")

    print(f"[전략 역추출] video_id={args.video_id}, backend={args.llm_backend}")
    result = extract_strategy(
        scenario,
        backend=args.llm_backend,
        gemini_model=args.gemini_model,
        codex_model=args.codex_model,
        timeout=args.timeout,
    )
    _warn_failures(result)

    result["_meta"] = {"video_id": args.video_id, "llm_backend": args.llm_backend}
    _save_json(video_dir / "strategy_analysis.json", result)
    print("완료.")


if __name__ == "__main__":
    main()
