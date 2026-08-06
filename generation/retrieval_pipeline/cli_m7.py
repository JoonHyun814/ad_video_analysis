"""retrieval_pipeline CLI — M7(장치 조립 → 대안 스토리라인 생성, LLM 1회 이상).

M6(cli_m6.py) 이 만든 쿼리별 장치를 모아 대안 스토리라인 + 비교/권고 + 공통 체크 + 다음 단계를
만든다. LLM 이 스스로 지금 가진 장치로는 부족하다고 판단하면(gap_assessment.sufficient=False)
--max_rounds 안에서 자동으로 M5~M6 를 한 번 더 돌려 장치를 보강한다(사용자 요청 — "m7 가 끝난
후 LLM 이 스스로 연출이 부족하다고 느낄 경우 추가 참조를 위한 retrieval 을 할 수 있도록").
재시도 라운드는 m5_r2.json/m6_r2.json 같은 파일로 그대로 남는다 — 무엇을 더 검색했고 무엇이
나왔는지 항상 파일로 확인할 수 있다. 이 파이프라인의 마지막 단계다.

사용법:
    python -m generation.retrieval_pipeline.cli_m7 --input <run_dir>/m6.json \\
        [--llm_backend cli|api] [--top_k 3] [--db_path output/vector_db] [--max_rounds 2] [--output ...]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from generation.retrieval_pipeline.pipeline import run_m7
from generation.v5_m0_m3 import llm_adapter


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="retrieval_pipeline M7 (장치 조립 → 스토리라인 생성)")
    p.add_argument("--input", type=Path, required=True, help="m6.json 경로")
    p.add_argument("--llm_backend", default="cli", choices=("cli", "api"),
                   help="텍스트 LLM 호출 방식 — cli: claude -p CLI(기본) | api: Anthropic API 직접 호출")
    p.add_argument("--top_k", type=int, default=3,
                   help="자동 재검색 라운드에서 쿼리 1개당 가져올 참조 광고 수(기본 3, 최대 20)")
    p.add_argument("--db_path", default="output/vector_db", help="ChromaDB 경로(자동 재검색 라운드용)")
    p.add_argument("--max_rounds", type=int, default=2,
                   help="M7 자가진단이 부족하다고 판단할 때 자동 재검색을 허용할 최대 라운드 수 "
                        "(기본 2 — 최초 1회 + 재시도 1회, 1이면 재시도 없이 첫 결과로 확정)")
    p.add_argument("--output", type=Path, default=None,
                   help="최종 Markdown 경로(기본: --input 과 같은 디렉터리의 creative_reference_ideas.md)")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    llm_adapter.set_backend(args.llm_backend)
    data = json.loads(args.input.read_text(encoding="utf-8"))

    result = run_m7(data, top_k=args.top_k, db_path=args.db_path, max_rounds=args.max_rounds)

    output_dir = args.input.parent
    markdown = result.pop("markdown")

    for extra in result.get("rounds", [])[1:]:
        n = extra["round"]
        (output_dir / f"m5_r{n}.json").write_text(
            json.dumps({"gap_note": extra.get("gap_note", ""), "search_queries": extra["search_queries"],
                       "search_results": extra["search_results"]}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        (output_dir / f"m6_r{n}.json").write_text(
            json.dumps({"prompt": extra["m6_prompt"], "devices": extra["devices"]}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"  저장(재시도 라운드 {n}): {output_dir / f'm5_r{n}.json'}, {output_dir / f'm6_r{n}.json'}")

    out_json = output_dir / "m7.json"
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {out_json}")

    out_md = args.output or (output_dir / "creative_reference_ideas.md")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(markdown, encoding="utf-8")
    print(f"  저장: {out_md}")


if __name__ == "__main__":
    main()
