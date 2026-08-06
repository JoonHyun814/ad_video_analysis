"""retrieval_pipeline CLI — M0(소재 인제스트)~M2(포지셔닝), v5_m0_m3 독립 구현.

v5_m0_m3 를 import 하지 않는다(사용자 요청 — "m0-m2 를 v5_m0_m3 거를 import 하는게 아니라
독립적으로 코드 새롭게 만들어서 사용"). **브랜드 가이드라인이 1차 소스**이고, 가이드라인에서
확인할 수 없는 정보만 --url 크롤로 보완한다 — 그래서 v5_m0_m3.cli.py 와 반대로 이 CLI는
`--guideline` 이 필수, `--url` 이 선택이다.

사용법:
    python -m generation.retrieval_pipeline.cli --guideline <가이드라인.md|txt> \\
        [--url <제품 상세페이지 URL>] [--llm_backend cli|api] [--output_dir ...]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from generation.retrieval_pipeline.pipeline import run_m0_m2
from generation.v5_m0_m3 import llm_adapter


def _slug(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "_", text).strip("_") or "run"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="retrieval_pipeline M0~M2 (가이드라인 1차 소스, 크롤은 보완)")
    p.add_argument("--guideline", type=Path, required=True,
                   help="브랜드 가이드라인 md/txt 경로 — M0의 1차 소스(제품명/USP/타깃 등)")
    p.add_argument("--url", default="",
                   help="제품 상세페이지 URL(선택) — 가이드라인에 없는 정보(제품 이미지 등)를 보완")
    p.add_argument("--llm_backend", default="cli", choices=("cli", "api"),
                   help="텍스트 LLM 호출 방식 — cli: claude -p CLI(기본) | api: Anthropic API 직접 호출")
    p.add_argument("--output_dir", type=Path, default=Path("output/retrieval_pipeline"), help="결과 저장 경로")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    llm_adapter.set_backend(args.llm_backend)
    if not args.guideline.exists():
        raise SystemExit(f"[오류] --guideline 파일 없음: {args.guideline}")
    guideline_text = args.guideline.read_text(encoding="utf-8")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    label = _slug(args.guideline.stem)

    result = run_m0_m2(guideline_text, url=args.url)
    if args.url:
        print(f"  크롤 보완: {args.url}" + (f" (실패: {result['crawl'].get('error')})" if result["crawl"].get("error") else ""))

    out_path = args.output_dir / f"{label}_m0_m2.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {out_path}")


if __name__ == "__main__":
    # Windows 콘솔(cp949)이 LLM 생성 텍스트의 특수문자(em dash 등)를 못 만나 print() 가
    # UnicodeEncodeError 로 죽는 것을 막는다 — 실제 파이프라인 로직은 이미 끝난 뒤의 요약 출력이
    # 죽는 것뿐이라 errors="replace" 로 깨진 문자만 대체하고 계속 진행한다.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    main()
