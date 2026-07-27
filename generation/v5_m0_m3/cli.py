"""v5_m0_m3 CLI — URL 하나로 M0(소재 인제스트)~M3(컨셉 발산)까지 실행한다.

사용법:
    python -m generation.v5_m0_m3.cli --url <제품 상세페이지 URL> [--producttitle ...] \\
        [--llm_backend cli|api] [--output_dir ...]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path

from generation.v5_m0_m3 import llm_adapter
from generation.v5_m0_m3.pipeline import run_m0_m3


def _slug(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "_", text).strip("_") or "run"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="v5 M0~M3 파이프라인 (소재 인제스트 → 인사이트 → 포지셔닝 → 컨셉 발산)")
    p.add_argument("--url", required=True, help="제품 상세페이지 URL")
    p.add_argument("--producttitle", default="", help="크롤 차단 시 web_search 복구에 쓸 제품 제목 힌트")
    p.add_argument("--llm_backend", default="cli", choices=("cli", "api"),
                   help="텍스트 LLM 호출 방식 — cli: claude -p CLI(기본, API 키 불필요) | "
                        "api: Anthropic API 직접 호출(env/api.env ANTHROPIC_API_KEY 필요)")
    p.add_argument("--output_dir", type=Path, default=Path("output/v5_m0_m3"), help="결과 저장 경로")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    llm_adapter.set_backend(args.llm_backend)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    label = _slug(args.producttitle or args.url)

    result = asyncio.run(run_m0_m3(args.url, producttitle=args.producttitle, label=label))

    out_path = args.output_dir / f"{label}_m0_m3.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {out_path}")

    if result.get("error"):
        raise SystemExit(f"[오류] {result['error']}")


if __name__ == "__main__":
    main()
