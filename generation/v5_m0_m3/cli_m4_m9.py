"""v5_m0_m3 CLI — M0~M3 결과(JSON)를 입력받아 M4(비평)~M9(콘티)까지 실행한다.

cli.py(M0~M3)와 완전히 분리된 별도 진입점이다 — 두 파이프라인을 독립적으로 실행할 수 있도록
설계했다. 입력은 `python -m generation.v5_m0_m3.cli` 가 만든 `*_m0_m3.json`
(`{"module0","m1","m2","m3"}`)이다.

사용법:
    python -m generation.v5_m0_m3.cli_m4_m9 --input output/v5_m0_m3/<slug>_m0_m3.json \\
        [--style cinematic] [--llm_backend cli|api] [--retrieval] [--select_concept "컨셉명"]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path

from generation.v5_m0_m3 import llm_adapter
from generation.v5_m0_m3.pipeline import run_m4_m9
from generation.v5_m0_m3.video_style import VALID as _VALID_STYLES


def _slug(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "_", text).strip("_") or "concept"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="v5 M4~M9 파이프라인 (비평·킬 → 스크립트 → 레드팀 → 검증 → 콘티)")
    p.add_argument("--input", required=True, type=Path,
                   help="run_m0_m3()/cli.py 가 만든 *_m0_m3.json 경로 ({module0,m1,m2,m3})")
    p.add_argument("--style", default="", choices=("", *_VALID_STYLES),
                   help="M9 콘티 촬영 포맷. 미지정 시 cinematic 기본값")
    p.add_argument("--llm_backend", default="cli", choices=("cli", "api"),
                   help="텍스트 LLM 호출 방식 — cli: claude -p CLI(기본, API 키 불필요) | "
                        "api: Anthropic API 직접 호출(env/api.env ANTHROPIC_API_KEY 필요)")
    p.add_argument("--retrieval", action="store_true",
                   help="M4~M9 에서도 evaluation/creative 크리에이티브 벡터 DB 검색 도구를 "
                        "LLM 에 제공한다 — M5(스크립트)/M9(콘티)는 반영 시 "
                        "referencedvideoid/referencedelement 로 추적되고, M4/M6/M7 은 "
                        "advisory 로만 열어둔다(강제 아님)")
    p.add_argument("--select_concept", default="",
                   help="M4 LLM 비평 대신, 입력 M3 concepts[] 중 이 이름과 일치하는 컨셉을 "
                        "사용자가 직접 GATE A 통과로 지정한다(M4 생략). 미지정 시 기존처럼 "
                        "M4 가 자율적으로 컨셉을 선택한다. 지정 시 결과 파일명에 컨셉 슬러그가 "
                        "붙어(<label>_<컨셉슬러그>_m4_m9.json) 같은 M3 로 여러 컨셉을 돌려도 "
                        "덮어쓰지 않는다")
    p.add_argument("--output_dir", type=Path, default=Path("output/v5_m0_m3"), help="결과 저장 경로")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    llm_adapter.set_backend(args.llm_backend)
    llm_adapter.set_retrieval(args.retrieval)
    if not args.input.exists():
        raise SystemExit(f"[오류] 입력 파일 없음: {args.input}")

    data = json.loads(args.input.read_text(encoding="utf-8"))
    missing = [k for k in ("module0", "m1", "m2", "m3") if k not in data]
    if missing:
        raise SystemExit(f"[오류] 입력 JSON 에 필요한 키가 없음: {missing} (run_m0_m3 결과가 아닌 것 같습니다)")

    label = args.input.stem.removesuffix("_m0_m3")
    if args.select_concept:
        label = f"{label}_{_slug(args.select_concept)}"
    args.output_dir.mkdir(parents=True, exist_ok=True)

    retrieval_log_path = None
    if args.retrieval:
        retrieval_log_path = args.output_dir / f"{label}_m4_m9_retrieval.jsonl"
        llm_adapter.set_retrieval_log(retrieval_log_path)

    try:
        result = asyncio.run(run_m4_m9(
            data["module0"], data["m1"], data["m2"], data["m3"],
            style=args.style or None, label=label, forced_concept=args.select_concept or None))
    except ValueError as e:
        raise SystemExit(f"[오류] {e}")

    out_path = args.output_dir / f"{label}_m4_m9.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {out_path}")
    print(f"  gates: {result.get('gates')}")
    if retrieval_log_path:
        print(f"  검색 도구 사용 기록: {retrieval_log_path}"
              f"{' (사용 없음)' if not retrieval_log_path.exists() else ''}")

    if result.get("error"):
        raise SystemExit(f"[오류] {result['error']}")


if __name__ == "__main__":
    main()
