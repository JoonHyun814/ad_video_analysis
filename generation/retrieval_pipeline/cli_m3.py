"""retrieval_pipeline CLI — M3(m0~m2 분석 + search_chromadb 자율 호출로 연출 장치 8개 완성).

M0~M2(cli.py) 다음 단계이자, 이 파이프라인이 처음으로 자체 LLM 호출을 수행하는 단계다. 한 줄
컨셉 원칙(--concept)은 선택이다 — 안 주면 m0~m2 맥락(포지셔닝 성명서·가치 제안)에서 LLM이
직접 크리에이티브 문제를 도출한다. 이 실행의 출력 폴더(output/retrieval_pipeline/<날짜>_
<제목>/)를 새로 만드는 단계이기도 하다 — 이후 단계는 --input 파일과 같은 디렉터리에 이어서
저장한다.

사용법:
    python -m generation.retrieval_pipeline.cli_m3 \\
        --input output/retrieval_pipeline/<slug>_m0_m2.json \\
        --title "DBH_15초_CTV" [--concept "..."] [--ad_length 15초] [--llm_backend cli|api]
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

from generation.retrieval_pipeline.pipeline import run_m3


def _slug(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "_", text).strip("_") or "run"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="retrieval_pipeline M3 (분석 + 도구 호출로 연출 장치 8개 완성)")
    p.add_argument("--input", type=Path, required=True, help="<slug>_m0_m2.json 경로(module0/m1/m2 포함)")
    p.add_argument("--concept", default="",
                   help='한 줄 크리에이티브 원칙(선택 — 안 주면 m0~m2 맥락에서 직접 도출)')
    p.add_argument("--title", required=True, help="출력 폴더명에 쓸 프로젝트 제목(슬러그화됨)")
    p.add_argument("--ad_length", default="15초", help="광고 길이(기본 15초)")
    p.add_argument("--llm_backend", default="cli", choices=("cli", "api"),
                   help="cli: claude -p + chromadb-explorer MCP(기본) | api: Anthropic API 직접 tool_use")
    p.add_argument("--output_dir", type=Path, default=Path("output/retrieval_pipeline"),
                   help="결과 저장 상위 경로 — 실제 산출물은 이 아래 <날짜>_<제목>/ 폴더에 생긴다")
    return p


def main() -> None:
    args = _build_parser().parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    if data.get("error"):
        raise SystemExit(f"[오류] 입력 파일에 error 있음 — M0~M2 부터 다시 확인: {data['error']}")

    title_slug = _slug(args.title)
    run_dir = args.output_dir / f"{date.today():%Y%m%d}_{title_slug}"
    run_dir.mkdir(parents=True, exist_ok=True)

    result = run_m3(data["module0"], data["m1"], data["m2"], concept_line=args.concept,
                    ad_length=args.ad_length, backend=args.llm_backend,
                    log_prefix=title_slug, log_dir=str(run_dir))

    out_path = run_dir / "m3.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {out_path}")
    print(f"  장치 {len(result['devices'])}개 생성됨")


if __name__ == "__main__":
    main()
