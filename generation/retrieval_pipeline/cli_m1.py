"""retrieval_pipeline CLI — M1(제품·브랜드 인사이트 조사).

이 파이프라인의 새 첫 단계다 — 실행 폴더(output/retrieval_pipeline/<날짜>_<제목>/)를
새로 만드는 책임이 cli_m3.py 에서 이쪽으로 옮겨왔다(cli_m3.py 는 이번 변경에서 손대지
않았다 — 여전히 독립적으로도 실행 가능).

사용법:
    python -m generation.retrieval_pipeline.cli_m1 \\
        --product_name "..." --url "<제품 상세페이지 URL>" --title "DBH_15초_CTV" \\
        [--guideline <가이드라인.md>] [--reference_dir <참조 이미지 폴더>] \\
        [--llm_backend cli|api]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import date
from pathlib import Path

from generation.retrieval_pipeline.pipeline import run_m1


def _slug(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "_", text).strip("_") or "run"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="retrieval_pipeline M1 (제품·브랜드 인사이트 조사)")
    p.add_argument("--product_name", required=True, help="제품명")
    p.add_argument("--url", required=True, help="제품 상세페이지 URL")
    p.add_argument("--title", required=True, help="출력 폴더명에 쓸 프로젝트 제목(슬러그화됨)")
    p.add_argument("--guideline", type=Path, default=None,
                   help="브랜드 가이드라인 md 경로 — 지정 시 최우선 근거로 프롬프트에 삽입")
    p.add_argument("--reference_dir", type=Path, default=None,
                   help="참조 이미지 폴더(여러 장) — 외관 묘사 근거로 OpenAI Vision 분석에 쓰인다")
    p.add_argument("--llm_backend", default="cli", choices=("cli", "api"),
                   help="cli: claude -p(기본) | api: Anthropic API 직접 호출")
    p.add_argument("--output_dir", type=Path, default=Path("output/retrieval_pipeline"),
                   help="결과 저장 상위 경로 — 실제 산출물은 이 아래 <날짜>_<제목>/ 폴더에 생긴다")
    return p


def main() -> None:
    args = _build_parser().parse_args()

    guideline_md = ""
    if args.guideline:
        if args.guideline.exists():
            guideline_md = args.guideline.read_text(encoding="utf-8")
            print(f"  가이드라인 적용(최우선 근거): {args.guideline}")
        else:
            raise SystemExit(f"[오류] --guideline 파일 없음: {args.guideline}")

    if args.reference_dir and not args.reference_dir.is_dir():
        raise SystemExit(f"[오류] --reference_dir 폴더 없음: {args.reference_dir}")

    title_slug = _slug(args.title)
    run_dir = args.output_dir / f"{date.today():%Y%m%d}_{title_slug}"
    run_dir.mkdir(parents=True, exist_ok=True)

    result = asyncio.run(run_m1(
        args.product_name, args.url, guideline_md=guideline_md,
        reference_dir=str(args.reference_dir) if args.reference_dir else None,
        backend=args.llm_backend, log_prefix=title_slug, log_dir=str(run_dir),
    ))

    out_path = run_dir / "m1.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {out_path}")
    print(f"  제품 종류: {result.get('product_type', '')}")
    n_images = len(result.get("crawled_images") or [])
    if n_images:
        print(f"  크롤링 이미지 저장: {n_images}개 → {run_dir / 'crawled_images'}")


if __name__ == "__main__":
    main()
