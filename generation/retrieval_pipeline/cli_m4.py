"""retrieval_pipeline CLI — M4(크리에이티브 문제 진단 + 연출 장치 후보·검색 쿼리 제안, LLM 1회).

M0~M2(cli.py) → M3(cli_m3.py, 현재 공백) 다음 단계. 여기서부터 M4~M7 이 독립 CLI로 나뉜다
(v5_m0_m3 의 cli.py/cli_m3.py/cli_m4_m9.py 분리와 같은 이유 — 비용이 큰 LLM 호출 단계를
고정해두고 뒷 단계만 몇 번이든 다시 돌릴 수 있게, 사용자 요청). 한 줄 컨셉 원칙을 처음 받는
단계이자, 이 실행의 출력 폴더(output/retrieval_pipeline/<날짜>_<제목>/)를 새로 만드는 단계이기도
하다 — 이후 cli_m5/cli_m6/cli_m7 은 --input 파일과 같은 디렉터리에 이어서 저장한다(cli_m3.py
와 동일한 관례).

사용법:
    python -m generation.retrieval_pipeline.cli_m4 \\
        --input output/retrieval_pipeline/<slug>_m0_m3.json \\
        --concept "기기를 보여주지 말고, 집에서 세계와 연결되는 순간을 보여라." \\
        --title "DBH_15초_CTV" [--ad_length 15초] [--llm_backend cli|api]
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

from generation.retrieval_pipeline.pipeline import run_m4
from generation.v5_m0_m3 import llm_adapter


def _slug(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "_", text).strip("_") or "run"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="retrieval_pipeline M4 (문제 진단 + 장치 후보·검색 쿼리 제안)")
    p.add_argument("--input", type=Path, required=True, help="<slug>_m0_m3.json 경로(module0/m1/m2/m3 포함)")
    p.add_argument("--concept", required=True,
                   help='한 줄 크리에이티브 원칙(예: "기기를 보여주지 말고, 집에서 세계와 연결되는 순간을 보여라.")')
    p.add_argument("--title", required=True, help="출력 폴더명에 쓸 프로젝트 제목(슬러그화됨)")
    p.add_argument("--ad_length", default="15초", help="광고 길이(기본 15초)")
    p.add_argument("--llm_backend", default="cli", choices=("cli", "api"),
                   help="텍스트 LLM 호출 방식 — cli: claude -p CLI(기본) | api: Anthropic API 직접 호출")
    p.add_argument("--output_dir", type=Path, default=Path("output/retrieval_pipeline"),
                   help="결과 저장 상위 경로 — 실제 산출물은 이 아래 <날짜>_<제목>/ 폴더에 생긴다")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    llm_adapter.set_backend(args.llm_backend)

    data = json.loads(args.input.read_text(encoding="utf-8"))
    if data.get("error"):
        raise SystemExit(f"[오류] 입력 파일에 error 있음 — M0~M2 부터 다시 확인: {data['error']}")

    run_dir = args.output_dir / f"{date.today():%Y%m%d}_{_slug(args.title)}"
    run_dir.mkdir(parents=True, exist_ok=True)

    result = run_m4(data["module0"], data["m1"], data["m2"], data.get("m3", {}),
                    args.concept, ad_length=args.ad_length)

    out_path = run_dir / "m4.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {out_path}")


if __name__ == "__main__":
    main()
