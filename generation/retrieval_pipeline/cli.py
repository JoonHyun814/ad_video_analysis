"""retrieval_pipeline CLI — M0(소재 인제스트)~M2(포지셔닝).

generation.v5_m0_m3.pipeline.run_m0_m2() 를 그대로 호출한다(사용자 요청 — "M0~M2는 v5_m0_m3과
동일"). 이 파일은 출력 경로 기본값만 이 파이프라인 전용(output/retrieval_pipeline)으로 바꾼
얇은 진입점이다 — M0~M2 로직 자체는 여기서 재구현하지 않는다.

사용법:
    python -m generation.retrieval_pipeline.cli --url <제품 상세페이지 URL> [--producttitle ...] \\
        [--llm_backend cli|api] [--output_dir ...] [--guideline <가이드라인.md>]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path

from generation.retrieval_pipeline.pipeline import run_m0_m2
from generation.v5_m0_m3 import llm_adapter


def _slug(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "_", text).strip("_") or "run"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="retrieval_pipeline M0~M2 (v5_m0_m3와 동일 로직 재사용)")
    p.add_argument("--url", required=True, help="제품 상세페이지 URL")
    p.add_argument("--producttitle", default="", help="크롤 차단 시 web_search 복구에 쓸 제품 제목 힌트")
    p.add_argument("--llm_backend", default="cli", choices=("cli", "api"),
                   help="텍스트 LLM 호출 방식 — cli: claude -p CLI(기본) | api: Anthropic API 직접 호출")
    p.add_argument("--output_dir", type=Path, default=Path("output/retrieval_pipeline"), help="결과 저장 경로")
    p.add_argument("--guideline", type=Path, default=None,
                   help="브랜드 가이드라인 md 경로 — 지정 시 MODULE 1·2 시스템 프롬프트에 최우선 지시로 삽입")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    llm_adapter.set_backend(args.llm_backend)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    label = _slug(args.producttitle or args.url)

    guideline_md = ""
    if args.guideline:
        if args.guideline.exists():
            guideline_md = args.guideline.read_text(encoding="utf-8")
            print(f"  가이드라인 적용(M1·M2 최우선 지시): {args.guideline}")
        else:
            raise SystemExit(f"[오류] --guideline 파일 없음: {args.guideline}")

    result = asyncio.run(run_m0_m2(args.url, producttitle=args.producttitle, label=label,
                                   guideline_md=guideline_md))

    out_path = args.output_dir / f"{label}_m0_m2.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {out_path}")

    if result.get("error"):
        raise SystemExit(f"[오류] {result['error']}")


if __name__ == "__main__":
    main()
