"""retrieval_pipeline CLI — M2(M1 인사이트 분석 + search_chromadb 자율 호출로 연출 장치 8개 완성).

M1(cli_m1.py) 다음 단계이자, 이 파이프라인이 두 번째로 자체 LLM 호출을 수행하는 단계다.
--m1_input(cli_m1.py 가 만든 m1.json — 제품 종류/외관/사용법/기능/재료/브랜드 이미지/타겟/
기타사항)이 이제 M2의 주 근거다(사용자 요청 — "M2는 이제 m0_m2 말고 m1을 토대로 작동"). 한 줄
컨셉 원칙(--concept)도 선택이다 — 안 주면 M1 인사이트(+있다면 m0~m2 포지셔닝)에서 LLM이
직접 크리에이티브 문제를 도출한다.

이 단계는 원래 이 파이프라인의 M3였다(사용자 요청 — "기존 m3 -> m2로 변경"). M1~M2 사이에
있던 번호 공백(legacy M2=v5_m0_m3 포지셔닝, 이 패키지에서는 아직 재설계 안 함)을 이 단계가
메우고, 비게 된 M3 번호는 새 단계(scenario_draft.py, M2 장치 2~4개 조합 → 러프 시나리오
초안 5개)가 가져갔다 — cli_m3.py 참고.

--input(legacy m0_m2.json, v5_m0_m3 M0~M2 재사용 경로)은 이제 선택이다 — module0 사실/
legacy m1(JTBD 인사이트)/m2(포지셔닝 성명서)로 M2 맥락을 더 보강하고 싶을 때만 넘긴다. 하나도
없이는 실행할 수 없으므로 --input 과 --m1_input 중 최소 하나는 있어야 한다.

출력 폴더: --m1_input 을 주면 그 m1.json 이 있던 폴더(cli_m1.py 가 만든 실행 폴더)에 그대로
m2.json 을 이어서 저장한다(cli_m3.py/cli_m4.py/cli_m5.py 와 같은 관례 — --title 불필요).
--m1_input 없이 --input(legacy)만 쓰면 이 실행이 새 날짜 폴더(output/retrieval_pipeline/
<날짜>_<제목>/)를 만드는 단계가 되므로 --title 이 필요하다.

사용법:
    # M1 인사이트를 근거로 실행(권장) — 같은 폴더에 m2.json 이어서 저장
    python -m generation.retrieval_pipeline.cli_m2 \\
        --m1_input output/retrieval_pipeline/<날짜>_<제목>/m1.json \\
        [--input <legacy m0_m2.json>] [--concept "..."] [--ad_length 15초] [--llm_backend cli|api]

    # legacy m0~m2 맥락만으로 실행(M1 없이) — 새 날짜 폴더 생성
    python -m generation.retrieval_pipeline.cli_m2 \\
        --input output/retrieval_pipeline/<slug>_m0_m2.json --title "DBH_15초_CTV" \\
        [--concept "..."] [--ad_length 15초] [--llm_backend cli|api]
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

from generation.retrieval_pipeline.pipeline import run_m2


def _slug(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "_", text).strip("_") or "run"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="retrieval_pipeline M2 (M1 인사이트 분석 + 도구 호출로 연출 장치 8개 완성)")
    p.add_argument("--m1_input", type=Path, default=None,
                   help="cli_m1.py 가 만든 m1.json 경로 — M2의 주 근거(제품 종류/외관/사용법/기능/재료/"
                        "브랜드 이미지/타겟/기타사항). --input 과 최소 하나는 필요")
    p.add_argument("--input", type=Path, default=None,
                   help="<slug>_m0_m2.json 경로(선택, legacy module0/m1/m2) — --m1_input 을 보강할 때만")
    p.add_argument("--concept", default="",
                   help='한 줄 크리에이티브 원칙(선택 — 안 주면 M1 인사이트/m0~m2 맥락에서 직접 도출)')
    p.add_argument("--title", default=None,
                   help="출력 폴더명에 쓸 프로젝트 제목(슬러그화) — --m1_input 을 주면 그 폴더를 그대로 "
                        "이어 쓰므로 생략 가능. --m1_input 없이 --input 만 쓸 때는 필수(새 폴더 생성)")
    p.add_argument("--ad_length", default="15초", help="광고 길이(기본 15초)")
    p.add_argument("--llm_backend", default="cli", choices=("cli", "api"),
                   help="cli: claude -p + chromadb-explorer MCP(기본) | api: Anthropic API 직접 tool_use")
    p.add_argument("--output_dir", type=Path, default=Path("output/retrieval_pipeline"),
                   help="--m1_input 없이 새 폴더를 만들 때만 쓰는 상위 경로 — 실제 산출물은 이 아래 "
                        "<날짜>_<제목>/ 폴더에 생긴다")
    return p


def main() -> None:
    args = _build_parser().parse_args()

    if not args.m1_input and not args.input:
        raise SystemExit("[오류] --m1_input 또는 --input 중 최소 하나는 있어야 합니다.")

    legacy: dict = {}
    if args.input:
        if not args.input.exists():
            raise SystemExit(f"[오류] --input 파일 없음: {args.input}")
        legacy = json.loads(args.input.read_text(encoding="utf-8"))
        if legacy.get("error"):
            raise SystemExit(f"[오류] --input 파일에 error 있음 — M0~M2 부터 다시 확인: {legacy['error']}")

    m1_insight = None
    if args.m1_input:
        if not args.m1_input.exists():
            raise SystemExit(f"[오류] --m1_input 파일 없음: {args.m1_input}")
        m1_insight = json.loads(args.m1_input.read_text(encoding="utf-8"))
        print(f"  M1 인사이트 적용: {args.m1_input}")

    if args.m1_input:
        run_dir = args.m1_input.parent
        title_slug = re.sub(r"^\d{8}_", "", run_dir.name) or "run"
        run_dir.mkdir(parents=True, exist_ok=True)
    else:
        if not args.title:
            raise SystemExit("[오류] --m1_input 없이 --input 만으로 실행하려면 --title 이 필요합니다(새 출력 폴더명).")
        title_slug = _slug(args.title)
        run_dir = args.output_dir / f"{date.today():%Y%m%d}_{title_slug}"
        run_dir.mkdir(parents=True, exist_ok=True)

    result = run_m2(legacy.get("module0"), legacy.get("m1"), legacy.get("m2"), m1_insight=m1_insight,
                    concept_line=args.concept, ad_length=args.ad_length, backend=args.llm_backend,
                    log_prefix=title_slug, log_dir=str(run_dir))

    out_path = run_dir / "m2.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {out_path}")
    print(f"  장치 {len(result['devices'])}개 생성됨")


if __name__ == "__main__":
    main()
