"""retrieval_pipeline CLI — M4(크리에이티브 문제 진단 + 검색기준 축별 검색 쿼리 제안, LLM 1회).

M0~M2(cli.py) → M3(cli_m3.py, 여기서 실행 폴더가 이미 만들어졌다) 다음 단계. 여기서부터 M4~M7
이 독립 CLI로 나뉜다(v5_m0_m3 의 cli.py/cli_m3.py/cli_m4_m9.py 분리와 같은 이유 — 비용이 큰
LLM 호출 단계를 고정해두고 뒷 단계만 몇 번이든 다시 돌릴 수 있게, 사용자 요청). --output_dir
을 생략하면 --input(m3.json)과 같은 디렉터리에 이어서 저장한다(cli_m5/cli_m6/cli_m7 과 동일한
관례).

한 줄 크리에이티브 원칙의 우선순위는 다음과 같다:
    1) --concept 를 직접 지정 — M3 산출물과 무관하게 이 문장을 그대로 쓴다.
    2) --select_concept "<technique>" — M3 의 concepts[] 중 그 기법으로 만든 문장을 쓴다
       (v5_m0_m3 의 cli_m4_m9.py `--select_concept` 와 같은 패턴).
    3) 아무것도 지정하지 않으면 — M3 의 concepts[] 중 aggregate_rank=1(페르소나 3명의 순위를
       취합했을 때 가장 적절했던 후보)을 자동으로 쓴다.
    M3가 아직 실행되지 않아 --input 의 m3.concepts 가 비어 있는데 1)·2)도 없으면 에러를 낸다.

사용법:
    python -m generation.retrieval_pipeline.cli_m4 \\
        --input output/retrieval_pipeline/<날짜>_<제목>/m3.json \\
        [--concept "..." | --select_concept "PAS 모델"] \\
        [--ad_length 15초] [--llm_backend cli|api]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from generation.retrieval_pipeline.pipeline import run_m4
from generation.v5_m0_m3 import llm_adapter


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="retrieval_pipeline M4 (문제 진단 + 검색기준 축별 검색 쿼리 제안)")
    p.add_argument("--input", type=Path, required=True, help="<날짜>_<제목>/m3.json 경로(context/m3 포함)")
    p.add_argument("--concept", default="",
                   help='한 줄 크리에이티브 원칙을 직접 지정(생략 시 M3 결과에서 고른다)')
    p.add_argument("--select_concept", default="",
                   help="M3 concepts[] 중 이 기법(technique)명과 일치하는 후보를 사용(예: \"PAS 모델\")."
                        " --concept 가 있으면 이 옵션은 무시된다")
    p.add_argument("--ad_length", default="15초", help="광고 길이(기본 15초)")
    p.add_argument("--llm_backend", default="cli", choices=("cli", "api"),
                   help="텍스트 LLM 호출 방식 — cli: claude -p CLI(기본) | api: Anthropic API 직접 호출")
    p.add_argument("--output_dir", type=Path, default=None,
                   help="결과 저장 경로(기본: --input 과 같은 디렉터리)")
    return p


def _resolve_concept_line(args: argparse.Namespace, m3: dict[str, Any]) -> str:
    if args.concept:
        return args.concept

    concepts = m3.get("concepts", [])
    if args.select_concept:
        for c in concepts:
            if c.get("technique") == args.select_concept:
                print(f"  --select_concept={args.select_concept!r} 사용: {c.get('concept_line')}")
                return c["concept_line"]
        raise SystemExit(
            f"[오류] --select_concept={args.select_concept!r} 와 일치하는 technique 을 "
            f"m3.concepts 에서 찾을 수 없음(후보: {[c.get('technique') for c in concepts]})"
        )

    if concepts:
        top = min(concepts, key=lambda c: c.get("aggregate_rank", 999))
        print(f"  --concept 미지정, M3 {top.get('aggregate_rank')}순위[{top.get('technique')}] 컨셉 사용: {top.get('concept_line')}")
        return top["concept_line"]

    raise SystemExit(
        "[오류] --concept 이 없고 입력 파일의 m3.concepts 도 비어 있습니다. "
        "--concept 을 직접 지정하거나 cli_m3 를 먼저 실행하세요."
    )


def main() -> None:
    args = _build_parser().parse_args()
    llm_adapter.set_backend(args.llm_backend)

    data = json.loads(args.input.read_text(encoding="utf-8"))
    if data.get("error"):
        raise SystemExit(f"[오류] 입력 파일에 error 있음 - M0~M2 부터 다시 확인: {data['error']}")

    concept_line = _resolve_concept_line(args, data.get("m3", {}))

    result = run_m4(data["context"], concept_line, ad_length=args.ad_length)

    output_dir = args.output_dir or args.input.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "m4.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {out_path}")


if __name__ == "__main__":
    main()
