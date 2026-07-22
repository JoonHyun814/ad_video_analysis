"""evaluation 통합 CLI — python -m evaluation.cli --mode <mode> [모드별 옵션]"""
import argparse
import importlib
import sys

_MODES: dict[str, tuple[str, str]] = {
    "brief": ("evaluation.brief.run", "scenario_analysis → brief_analysis.json"),
    "parsed": ("evaluation.parsed.run", "파이프라인 산출물 종합 → parsed_analysis.json"),
    "scenario_eval": ("evaluation.scenario_eval.run", "시나리오 평가 → evaluation.json"),
    "category": ("evaluation.category.run", "카테고리 분석 + video_category 벡터 적재"),
    "concept": ("evaluation.concept.run", "컨셉 추출 + video_concept/facet 벡터 적재"),
    "creative": ("evaluation.creative.run", "크리에이티브 요소 추출 + 클리셰 리포트"),
    "strategy": ("evaluation.strategy.run", "M1·M2·M3 전략 역추출 → strategy_analysis.json"),
    "convert": ("evaluation.convert.convert", "parsed/brief → 외부 스키마 일괄 변환"),
    "convert_v2": ("evaluation.convert.convert_v2", "parsed → wrapped 스키마 변환"),
    "rename": ("evaluation.convert.rename_to_original", "결과 파일을 DB original_filename 으로 재명명"),
}


def _mode_help() -> str:
    lines = ["사용 가능한 모드:"]
    lines += [f"  {name:<13} {desc}" for name, (_, desc) in _MODES.items()]
    lines.append("모드별 옵션: python -m evaluation.cli --mode <mode> -h")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="evaluation.cli",
        description="evaluation 통합 CLI",
        epilog=_mode_help(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    parser.add_argument("--mode", choices=_MODES, help="실행할 파이프라인 모드")
    parser.add_argument("-h", "--help", action="store_true", help="도움말 출력")
    args, rest = parser.parse_known_args()

    if args.mode is None:
        parser.print_help()
        sys.exit(0 if args.help else 1)
    if args.help:
        rest.append("-h")

    module = importlib.import_module(_MODES[args.mode][0])
    module.main(rest)


if __name__ == "__main__":
    main()
