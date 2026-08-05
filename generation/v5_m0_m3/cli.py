"""v5_m0_m3 CLI — URL 하나로 M0(소재 인제스트)~M2(포지셔닝)까지 실행한다.

M3(컨셉 발산)는 별도 진입점 `cli_m3.py`로 분리했다 — M0~M2 는 크롤·LLM 호출 비용이 커서
한 번 고정해두고, 그 위에서 M3 만 여러 번(리롤·--retrieval on/off 비교 등) 다시 돌리고
싶을 때가 많기 때문이다(사용자 요청).

사용법:
    python -m generation.v5_m0_m3.cli --url <제품 상세페이지 URL> [--producttitle ...] \\
        [--llm_backend cli|api] [--output_dir ...] [--guideline <가이드라인.md>]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path

from generation.v5_m0_m3 import llm_adapter
from generation.v5_m0_m3.pipeline import run_m0_m2


def _slug(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "_", text).strip("_") or "run"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="v5 M0~M2 파이프라인 (소재 인제스트 → 인사이트 → 포지셔닝)")
    p.add_argument("--url", required=True, help="제품 상세페이지 URL")
    p.add_argument("--producttitle", default="", help="크롤 차단 시 web_search 복구에 쓸 제품 제목 힌트")
    p.add_argument("--llm_backend", default="cli", choices=("cli", "api"),
                   help="텍스트 LLM 호출 방식 — cli: claude -p CLI(기본, API 키 불필요) | "
                        "api: Anthropic API 직접 호출(env/api.env ANTHROPIC_API_KEY 필요)")
    p.add_argument("--output_dir", type=Path, default=Path("output/v5_m0_m3"), help="결과 저장 경로")
    p.add_argument("--guideline", type=Path, default=None,
                   help="브랜드 광고 목표 가이드라인 md 파일 경로. 지정하면 MODULE 1·2 시스템 "
                        "프롬프트 맨 끝에 '위의 모든 지시(오버라이드·사용자 커스텀 지시 포함)와 "
                        "충돌하면 이 가이드라인을 따른다'는 최우선 고정 지시로 삽입된다(JSON "
                        "스키마·형식 규칙은 그대로 유지)")
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
