"""retrieval_pipeline CLI — M4(M3 장치 조합 → 광고 전체 시나리오 완성, scenario_analysis.json
과 동일한 구조).

M3(cli_m3.py) 다음 단계. m3.json(context + creative_problem + devices 8개, module0/m1/m2
원본은 m3.json에 더 이상 저장되지 않는다 — pipeline.py 모듈 docstring 참고)을 읽어, LLM이
그중 이 제품·광고 길이에 맞는 장치를 골라 하나의 시나리오로 조합한다 —
`search_chromadb` 도구로 비슷한 길이의 광고 컷 구성·페이싱을 참고할 수도 있다(선택, MCP로
자율 호출). 새 날짜 폴더를 만들지 않고 --input 파일과 같은 디렉터리에 m4.json으로 저장한다
(pipeline.py 모듈 docstring의 관례 — 이후 단계는 이어서 같은 폴더에 쌓인다).

사용법:
    python -m generation.retrieval_pipeline.cli_m4 \\
        --input output/retrieval_pipeline/<날짜>_<제목>/m3.json [--llm_backend cli|api]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from generation.retrieval_pipeline.pipeline import run_m4


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="retrieval_pipeline M4(M3 장치 조합 → 광고 전체 시나리오)")
    p.add_argument("--input", type=Path, required=True,
                   help="m3.json 경로(context/creative_problem/devices 포함, module0/m1/m2 원본은 없음)")
    p.add_argument("--llm_backend", default="cli", choices=("cli", "api"),
                   help="cli: claude -p + chromadb-explorer MCP(기본) | api: Anthropic API 직접 tool_use")
    return p


def main() -> None:
    args = _build_parser().parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    if data.get("error"):
        raise SystemExit(f"[오류] 입력 파일에 error 있음 — M3 부터 다시 확인: {data['error']}")
    if not data.get("devices"):
        raise SystemExit("[오류] 입력 파일에 devices 가 없음 — cli_m3.py 를 먼저 실행하세요.")

    run_dir = args.input.parent
    # cli_m3.py 가 만든 실행 폴더명("<날짜>_<제목슬러그>")에서 제목 슬러그만 다시 뽑아
    # log_prefix 로 쓴다(M3 검색 로그와 파일이 섞이지 않도록 "_m4" 를 붙인다).
    title_slug = re.sub(r"^\d{8}_", "", run_dir.name) or "run"
    log_prefix = f"{title_slug}_m4"

    # m3.json 은 더 이상 module0/m1/m2 원본을 담지 않는다(사용자 요청) — 있으면(구버전
    # m3.json 과의 하위호환) 쓰고, 없으면 빈 dict.
    result = run_m4(data.get("module0") or {}, data.get("m1") or {}, data.get("m2") or {},
                    data["context"], data["creative_problem"], data["devices"],
                    concept_line=data.get("concept_line", ""), ad_length=data.get("ad_length", "15초"),
                    backend=args.llm_backend, log_prefix=log_prefix, log_dir=str(run_dir))

    out_path = run_dir / "m4.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {out_path}")
    print(f"  씬 {len(result['scenes'])}개, 사용 장치 {len(result['devices_applied'])}개")


if __name__ == "__main__":
    main()
