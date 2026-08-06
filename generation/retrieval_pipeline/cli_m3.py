"""retrieval_pipeline CLI — M3(발산 기법 7종으로 한 줄 컨셉 후보 생성 + 자가평가·순위, LLM 1회).

generation/docs/m3_concept.md 의 7개 발산 기법(경험 은유/리프레이밍/디스럽션/환유·제유/JTBD/
PAS/의인화) 각각으로 정확히 하나씩 한 줄 크리에이티브 컨셉을 만들고, 적절성을 스스로 평가해
순위를 매긴다. cli_m4.py 는 `--concept` 를 생략하면 이 중 rank=1을 자동으로 쓴다.

사용법:
    python -m generation.retrieval_pipeline.cli_m3 --input output/retrieval_pipeline/<slug>_m0_m2.json \\
        [--llm_backend cli|api]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from generation.retrieval_pipeline.pipeline import run_m3
from generation.v5_m0_m3 import llm_adapter


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="retrieval_pipeline M3 (발산 기법 7종 컨셉 생성 + 순위)")
    p.add_argument("--input", type=Path, required=True, help="<slug>_m0_m2.json 경로")
    p.add_argument("--llm_backend", default="cli", choices=("cli", "api"),
                   help="텍스트 LLM 호출 방식 — cli: claude -p CLI(기본) | api: Anthropic API 직접 호출")
    p.add_argument("--output_dir", type=Path, default=None,
                   help="결과 저장 경로(기본: --input 과 같은 디렉터리)")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    llm_adapter.set_backend(args.llm_backend)
    data = json.loads(args.input.read_text(encoding="utf-8"))
    if data.get("error"):
        raise SystemExit(f"[오류] 입력 파일에 error 있음 — M0~M2 부터 다시 확인: {data['error']}")

    result = run_m3(data["module0"], data["m1"], data["m2"])

    output_dir = args.output_dir or args.input.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = args.input.stem.removesuffix("_m0_m2")
    out_path = output_dir / f"{slug}_m0_m3.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {out_path}")

    for c in sorted(result["m3"]["concepts"], key=lambda c: c.get("rank", 999)):
        print(f"  [{c.get('rank')}위][{c.get('technique')}] {c.get('concept_line')}")


if __name__ == "__main__":
    main()
