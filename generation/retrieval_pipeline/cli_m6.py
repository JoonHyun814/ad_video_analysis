"""retrieval_pipeline CLI — M6(검색 결과 반영, 최종 문서 JSON 합성, LLM 1회).

M5(cli_m5.py)가 실제로 검색한 결과를 근거로 장치별 레퍼런스 인용·대안 스토리라인·비교/권고·
공통 체크·다음 단계를 완성한다. 이 호출의 user 프롬프트에 실제로 들어가는 값(검색 결과 포함)이
"실제 모델에 입력되는 데이터"다 — m6.json 의 `prompt` 키에 system/user 원문이 그대로 남는다.

사용법:
    python -m generation.retrieval_pipeline.cli_m6 --input <run_dir>/m5.json [--llm_backend cli|api]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from generation.retrieval_pipeline.pipeline import run_m6
from generation.v5_m0_m3 import llm_adapter


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="retrieval_pipeline M6 (검색 결과 반영 최종 문서 JSON)")
    p.add_argument("--input", type=Path, required=True, help="m5.json 경로(searches 포함)")
    p.add_argument("--llm_backend", default="cli", choices=("cli", "api"),
                   help="텍스트 LLM 호출 방식 — cli: claude -p CLI(기본) | api: Anthropic API 직접 호출")
    p.add_argument("--output_dir", type=Path, default=None, help="결과 저장 경로(기본: --input 과 같은 디렉터리)")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    llm_adapter.set_backend(args.llm_backend)
    data = json.loads(args.input.read_text(encoding="utf-8"))

    result = run_m6(data)

    output_dir = args.output_dir or args.input.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "m6.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {out_path}")


if __name__ == "__main__":
    main()
