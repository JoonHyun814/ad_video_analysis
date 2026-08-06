"""retrieval_pipeline CLI — M3(발산 기법 7종 컨셉 생성 → 페르소나 3명이 순위 매김 → 취합, LLM 5회).

generation/docs/m3_concept.md 의 7개 발산 기법(경험 은유/리프레이밍/디스럽션/환유·제유/JTBD/
PAS/의인화) 각각으로 정확히 하나씩 한 줄 크리에이티브 컨셉을 만들고, 타깃 그룹에 맞는 페르소나
3명을 만들어 각자 독립적으로 7개 컨셉의 순위를 매기게 한 뒤, 코드가 평균으로 최종 순위를
취합한다(concept_scout.py 참고). cli_m4.py 는 `--concept`/`--select_concept` 를 생략하면 이
중 aggregate_rank=1을 자동으로 쓴다.

이 파이프라인의 실행 폴더(output/retrieval_pipeline/<날짜>_<제목>/)를 새로 만드는 단계이기도
하다 — 이후 cli_m4~cli_m7 은 --input 파일과 같은 디렉터리에 이어서 저장한다.

사용법:
    python -m generation.retrieval_pipeline.cli_m3 \\
        --input output/retrieval_pipeline/<slug>_m0_m2.json \\
        --title "DBH_15초_CTV" [--llm_backend cli|api]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

from generation.retrieval_pipeline.pipeline import run_m3
from generation.v5_m0_m3 import llm_adapter


def _slug(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "_", text).strip("_") or "run"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="retrieval_pipeline M3 (발산 기법 7종 컨셉 생성 + 페르소나 순위 취합)")
    p.add_argument("--input", type=Path, required=True, help="<slug>_m0_m2.json 경로")
    p.add_argument("--title", required=True, help="출력 폴더명에 쓸 프로젝트 제목(슬러그화됨)")
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
        raise SystemExit(f"[오류] 입력 파일에 error 있음 - M0~M2 부터 다시 확인: {data['error']}")

    result = run_m3(data["module0"], data["m1"], data["m2"])

    run_dir = args.output_dir / f"{date.today():%Y%m%d}_{_slug(args.title)}"
    run_dir.mkdir(parents=True, exist_ok=True)
    out_path = run_dir / "m3.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {out_path}")

    print("  페르소나 3명:")
    for p in result["m3"]["personas"]:
        print(f"    - {p.get('name')}: {p.get('priorities')}")
    print("  컨셉 순위(취합 결과):")
    for c in sorted(result["m3"]["concepts"], key=lambda c: c.get("aggregate_rank", 999)):
        print(f"    [{c.get('aggregate_rank')}위][{c.get('technique')}] {c.get('concept_line')}")


if __name__ == "__main__":
    # Windows 콘솔(cp949)이 LLM 생성 텍스트의 특수문자(em dash 등)를 못 만나 print() 가
    # UnicodeEncodeError 로 죽는 것을 막는다 — 실제 파이프라인 로직은 이미 끝난 뒤의 요약 출력이
    # 죽는 것뿐이라 errors="replace" 로 깨진 문자만 대체하고 계속 진행한다.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    main()
