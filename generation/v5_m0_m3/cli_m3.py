"""v5_m0_m3 CLI — M0~M2 결과(JSON)를 입력받아 M3(컨셉 발산)만 실행한다.

cli.py(M0~M2)와 분리된 진입점이다 — M0~M2 를 한 번 고정해두고 그 위에서 M3 만 여러 번
(리롤·--retrieval on/off 비교 등) 다시 돌릴 수 있게 하려는 사용자 요청. 입력은
`python -m generation.v5_m0_m3.cli` 가 만든 `*_m0_m2.json`(`{"module0","m1","m2"}`)이다.
출력 `*_m0_m3.json`(`{"module0","m1","m2","m3"}`)은 `cli_m4_m9.py` 의 입력 형식과 동일하다.

사용법:
    python -m generation.v5_m0_m3.cli_m3 --input output/v5_m0_m3/<slug>_m0_m2.json \\
        [--llm_backend cli|api] [--retrieval] [--output_dir ...]
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from generation.v5_m0_m3 import llm_adapter
from generation.v5_m0_m3.pipeline import run_m3


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="v5 M3 파이프라인 (컨셉 발산, M0~M2 고정 입력 위에서 단독 실행)")
    p.add_argument("--input", required=True, type=Path,
                   help="run_m0_m2()/cli.py 가 만든 *_m0_m2.json 경로 ({module0,m1,m2})")
    p.add_argument("--llm_backend", default="cli", choices=("cli", "api"),
                   help="텍스트 LLM 호출 방식 — cli: claude -p CLI(기본, API 키 불필요) | "
                        "api: Anthropic API 직접 호출(env/api.env ANTHROPIC_API_KEY 필요)")
    p.add_argument("--retrieval", action="store_true",
                   help="M3(컨셉 발산)에서 ad_concept_reference 벡터 DB의 기존 광고 전략(소구·"
                        "포지셔닝·타겟)을 검색하는 도구(creative-retrieval MCP)를 LLM 에 제공한다. "
                        "어떤 세그먼트로 몇 건을 검색할지는 LLM 이 판단한다(강제 아님)")
    p.add_argument("--output_dir", type=Path, default=None,
                   help="결과 저장 경로. 미지정 시 --input 과 같은 디렉터리에 저장한다")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    llm_adapter.set_backend(args.llm_backend)
    llm_adapter.set_retrieval(args.retrieval)
    if not args.input.exists():
        raise SystemExit(f"[오류] 입력 파일 없음: {args.input}")

    data = json.loads(args.input.read_text(encoding="utf-8"))
    missing = [k for k in ("module0", "m1", "m2") if k not in data]
    if missing:
        raise SystemExit(f"[오류] 입력 JSON 에 필요한 키가 없음: {missing} (run_m0_m2 결과가 아닌 것 같습니다)")

    label = args.input.stem.removesuffix("_m0_m2")
    output_dir = args.output_dir or args.input.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    retrieval_log_path = None
    if args.retrieval:
        retrieval_log_path = output_dir / f"{label}_retrieval.jsonl"
        llm_adapter.set_retrieval_log(retrieval_log_path)

    result = asyncio.run(run_m3(data["module0"], data["m1"], data["m2"], label=label))

    out_path = output_dir / f"{label}_m0_m3.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {out_path}")
    if retrieval_log_path:
        print(f"  검색 도구 사용 기록: {retrieval_log_path}"
              f"{' (사용 없음)' if not retrieval_log_path.exists() else ''}")

    if result.get("error"):
        raise SystemExit(f"[오류] {result['error']}")


if __name__ == "__main__":
    main()
