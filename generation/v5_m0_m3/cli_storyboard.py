"""v5_m0_m3 CLI — M4~M9 결과(JSON)를 입력받아 AITIVE 스토리보드 HTML 양식을 채운다.

입력은 `cli_m4_m9.py` 가 만든 `<label>_m4_m9.json`(`{"m3","m4","m5","m6","m7","m9","gates"}`)
이다. 이 파일엔 module0/m1/m2 가 없으므로(브랜드·제품명·타깃 등에 필요), 같은 디렉터리에
있는 짝 파일 `<label>_m0_m3.json`(`cli.py` 산출물)을 관례대로 자동으로 찾아 함께 읽는다 —
다른 위치에 있으면 `--m0_m3` 로 직접 지정한다.

사용법:
    python -m generation.v5_m0_m3.cli_storyboard --input output/v5_m0_m3/<slug>_m4_m9.json \\
        [--m0_m3 <slug>_m0_m3.json 경로] [--llm_backend cli|api] [--retrieval] [--output <out.html>]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from generation.v5_m0_m3 import llm_adapter, storyboard_fill, storyboard_render


def _default_m0_m3_path(m4_m9_path: Path) -> Path:
    label = m4_m9_path.stem.removesuffix("_m4_m9")
    return m4_m9_path.with_name(f"{label}_m0_m3.json")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="M4~M9 결과로 AITIVE 스토리보드 HTML 양식 채우기")
    p.add_argument("--input", required=True, type=Path,
                   help="cli_m4_m9.py 가 만든 <label>_m4_m9.json 경로")
    p.add_argument("--m0_m3", type=Path, default=None,
                   help="cli.py 가 만든 <label>_m0_m3.json 경로(미지정 시 --input 과 같은 "
                        "디렉터리에서 <label>_m0_m3.json 을 관례로 찾는다)")
    p.add_argument("--llm_backend", default="cli", choices=("cli", "api"),
                   help="추가 기획 필드(캐릭터·제품·환경·카메라·조명·메타데이터)를 채우는 "
                        "LLM 호출 방식")
    p.add_argument("--retrieval", action="store_true",
                   help="추가 기획 필드를 채울 때 ad_production_reference 벡터 DB의 기존 광고 "
                        "캐스팅·카메라·조명 연출을 검색하는 도구를 LLM 에 제공한다(강제 아님)")
    p.add_argument("--output", type=Path, default=None,
                   help="결과 HTML 경로(미지정 시 --input 과 같은 디렉터리에 "
                        "<label>_storyboard.html 로 저장)")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    if not args.input.exists():
        raise SystemExit(f"[오류] 입력 파일 없음: {args.input}")

    m4_m9 = json.loads(args.input.read_text(encoding="utf-8"))
    missing = [k for k in ("m4", "m5", "m9") if k not in m4_m9]
    if missing:
        raise SystemExit(f"[오류] 입력 JSON 에 필요한 키가 없음: {missing} "
                          f"(cli_m4_m9.py 결과가 아닌 것 같습니다)")

    m0_m3_path = args.m0_m3 or _default_m0_m3_path(args.input)
    if not m0_m3_path.exists():
        raise SystemExit(f"[오류] module0/m1/m2 를 읽을 짝 파일이 없음: {m0_m3_path} "
                          f"(--m0_m3 로 직접 지정하세요)")
    m0_m3 = json.loads(m0_m3_path.read_text(encoding="utf-8"))

    llm_adapter.set_backend(args.llm_backend)
    llm_adapter.set_retrieval(args.retrieval)
    label = args.input.stem.removesuffix("_m4_m9")
    if args.retrieval:
        llm_adapter.set_retrieval_log(args.input.with_name(f"{label}_storyboard_retrieval.jsonl"))
    extra = storyboard_fill.fill_extra_fields(
        m0_m3.get("module0", {}), m0_m3.get("m1", {}), m0_m3.get("m2", {}),
        m4_m9.get("m4", {}), m4_m9.get("m5", {}), m4_m9.get("m9", {}))

    html = storyboard_render.render_storyboard_html(
        m0_m3.get("module0", {}), m0_m3.get("m1", {}), m0_m3.get("m2", {}),
        m4_m9.get("m4", {}), m4_m9.get("m5", {}), m4_m9.get("m9", {}), extra)

    out_path = args.output or args.input.with_name(f"{label}_storyboard.html")
    out_path.write_text(html, encoding="utf-8")
    print(f"  저장: {out_path}")


if __name__ == "__main__":
    main()
