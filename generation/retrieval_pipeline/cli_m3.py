"""retrieval_pipeline CLI — M3(컨셉 발산) placeholder.

M3는 아직 설계되지 않았다(사용자 요청 — "M3는 일단 공백으로 남기고"). 이 진입점은 M3 LLM 호출
없이 <slug>_m0_m2.json 을 그대로 받아 <slug>_m0_m3.json 계약 형태({"module0","m1","m2","m3"})만
맞춰 다음 단계(cli_m4.py)가 그대로 소비할 수 있게 한다. 나중에 M3를 구현하면 이 파일의
run_m3_blank() 호출부만 실제 M3 실행으로 교체하면 된다.

사용법:
    python -m generation.retrieval_pipeline.cli_m3 --input output/retrieval_pipeline/<slug>_m0_m2.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from generation.retrieval_pipeline.pipeline import run_m3_blank


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="retrieval_pipeline M3 placeholder (공백)")
    p.add_argument("--input", type=Path, required=True, help="<slug>_m0_m2.json 경로")
    p.add_argument("--output_dir", type=Path, default=None,
                   help="결과 저장 경로(기본: --input 과 같은 디렉터리)")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    if data.get("error"):
        raise SystemExit(f"[오류] 입력 파일에 error 있음 — M0~M2 부터 다시 확인: {data['error']}")

    result = run_m3_blank(data["module0"], data["m1"], data["m2"])

    output_dir = args.output_dir or args.input.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = args.input.stem.removesuffix("_m0_m2")
    out_path = output_dir / f"{slug}_m0_m3.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {out_path} (M3는 공백 placeholder)")


if __name__ == "__main__":
    main()
