"""v5_m0_m3 CLI — M0~M3 결과(JSON)를 입력받아 M4(비평)~M9(콘티)까지 실행한다.

cli.py(M0~M3)와 완전히 분리된 별도 진입점이다 — 두 파이프라인을 독립적으로 실행할 수 있도록
설계했다. 입력은 `python -m generation.v5_m0_m3.cli` 가 만든 `*_m0_m3.json`
(`{"module0","m1","m2","m3"}`)이다.

사용법:
    python -m generation.v5_m0_m3.cli_m4_m9 --input output/v5_m0_m3/<slug>_m0_m3.json \\
        [--style cinematic] [--llm_backend cli|api]
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from generation.v5_m0_m3 import llm_adapter
from generation.v5_m0_m3.pipeline import run_m4_m9
from generation.v5_m0_m3.video_style import VALID as _VALID_STYLES


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="v5 M4~M9 파이프라인 (비평·킬 → 스크립트 → 레드팀 → 검증 → 콘티)")
    p.add_argument("--input", required=True, type=Path,
                   help="run_m0_m3()/cli.py 가 만든 *_m0_m3.json 경로 ({module0,m1,m2,m3})")
    p.add_argument("--style", default="", choices=("", *_VALID_STYLES),
                   help="M9 콘티 촬영 포맷. 미지정 시 cinematic 기본값")
    p.add_argument("--llm_backend", default="cli", choices=("cli", "api"),
                   help="텍스트 LLM 호출 방식 — cli: claude -p CLI(기본, API 키 불필요) | "
                        "api: Anthropic API 직접 호출(env/api.env ANTHROPIC_API_KEY 필요)")
    p.add_argument("--output_dir", type=Path, default=Path("output/v5_m0_m3"), help="결과 저장 경로")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    llm_adapter.set_backend(args.llm_backend)
    if not args.input.exists():
        raise SystemExit(f"[오류] 입력 파일 없음: {args.input}")

    data = json.loads(args.input.read_text(encoding="utf-8"))
    missing = [k for k in ("module0", "m1", "m2", "m3") if k not in data]
    if missing:
        raise SystemExit(f"[오류] 입력 JSON 에 필요한 키가 없음: {missing} (run_m0_m3 결과가 아닌 것 같습니다)")

    label = args.input.stem.removesuffix("_m0_m3")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    result = asyncio.run(run_m4_m9(
        data["module0"], data["m1"], data["m2"], data["m3"],
        style=args.style or None, label=label))

    out_path = args.output_dir / f"{label}_m4_m9.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {out_path}")
    print(f"  gates: {result.get('gates')}")

    if result.get("error"):
        raise SystemExit(f"[오류] {result['error']}")


if __name__ == "__main__":
    main()
