"""retrieval_pipeline CLI — M7(최종 문서 렌더링, Markdown, LLM 아님).

M6(cli_m6.py) 의 구조화 출력을 generation/docs/DBH_Creative_Reference_Ideas.md 와 같은 형식의
Markdown 문서로 렌더링한다. 이 파이프라인의 마지막 단계다.

사용법:
    python -m generation.retrieval_pipeline.cli_m7 --input <run_dir>/m6.json [--output ...]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from generation.retrieval_pipeline.pipeline import run_m7


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="retrieval_pipeline M7 (최종 문서 Markdown 렌더링)")
    p.add_argument("--input", type=Path, required=True, help="m6.json 경로")
    p.add_argument("--output", type=Path, default=None,
                   help="출력 .md 경로(기본: --input 과 같은 디렉터리의 creative_reference_ideas.md)")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))

    markdown = run_m7(data)

    out_path = args.output or (args.input.parent / "creative_reference_ideas.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")
    print(f"  저장: {out_path}")


if __name__ == "__main__":
    main()
