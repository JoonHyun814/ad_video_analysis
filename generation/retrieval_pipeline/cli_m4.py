"""retrieval_pipeline CLI — M4(M3 초안 정교화 → 광고 전체 시나리오 완성, 최소 5컷).

M3(cli_m3.py) 다음 단계. m3.json(context + creative_problem + devices 8개 + drafts 5개)을
읽어, `--draft`로 고른 초안 하나를 정교화해 최소 5개 컷짜리 광고 전체 시나리오를 완성한다
(사용자 요청 — "m3의 drafts 리스트 중 하나를 정해서 입력으로 넣으면 ... 컷별 화면구성, 동적
연출, 대사, 나레이션, 자막, 사운드가 들어간 5개 이상의 컷으로 구성된 결과"). M1 인사이트는
m3.json의 context.product_insight(M2가 --m1_input을 받았다면 이미 들어있다)를 통해 함께
전달된다 — 별도 인자 없이 이미 프롬프트에 포함된다.

`search_chromadb` 도구로 비슷한 길이의 광고 컷 구성·페이싱을 참고할 수도 있다(선택, MCP로
자율 호출). 새 날짜 폴더를 만들지 않고 --input 파일과 같은 디렉터리에 m4.json으로 저장한다
(pipeline.py 모듈 docstring의 관례 — 이후 단계는 이어서 같은 폴더에 쌓인다).

사용법:
    python -m generation.retrieval_pipeline.cli_m4 \\
        --input output/retrieval_pipeline/<날짜>_<제목>/m3.json \\
        [--draft 0] [--llm_backend cli|api]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from generation.retrieval_pipeline.pipeline import run_m4


def _select_draft(drafts: list[dict], selector: str) -> dict:
    """selector 를 0부터 시작하는 인덱스로 먼저 해석하고, 정수가 아니면 drafts[].name 부분
    일치(대소문자 무시)로 찾는다 — 사용자가 "m3의 drafts 리스트 중 하나를 정해서" 넘길 수
    있게 하는 선택 로직."""
    try:
        idx = int(selector)
    except ValueError:
        idx = None
    if idx is not None:
        if 0 <= idx < len(drafts):
            return drafts[idx]
        raise SystemExit(f"[오류] --draft 인덱스 범위 초과(0~{len(drafts) - 1}): {selector}")
    needle = selector.strip().casefold()
    for d in drafts:
        if needle in str(d.get("name") or "").strip().casefold():
            return d
    names = [d.get("name") for d in drafts]
    raise SystemExit(f"[오류] --draft 이름과 일치하는 초안 없음: {selector!r} (후보: {names})")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="retrieval_pipeline M4(M3 초안 정교화 → 광고 전체 시나리오, 최소 5컷)")
    p.add_argument("--input", type=Path, required=True,
                   help="m3.json 경로(context/creative_problem/devices/drafts 포함)")
    p.add_argument("--draft", default="0",
                   help="사용할 M3 초안 — drafts[] 의 인덱스(0부터, 기본값 0) 또는 name 부분 문자열")
    p.add_argument("--llm_backend", default="cli", choices=("cli", "api"),
                   help="cli: claude -p + chromadb-explorer MCP(기본) | api: Anthropic API 직접 tool_use")
    return p


def main() -> None:
    args = _build_parser().parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    if data.get("error"):
        raise SystemExit(f"[오류] 입력 파일에 error 있음 — M3 부터 다시 확인: {data['error']}")
    if not data.get("devices"):
        raise SystemExit("[오류] 입력 파일에 devices 가 없음 — cli_m2.py 를 먼저 실행하세요.")
    drafts = data.get("drafts") or []
    if not drafts:
        raise SystemExit("[오류] 입력 파일에 drafts 가 없음 — cli_m3.py 를 먼저 실행하세요.")

    draft = _select_draft(drafts, args.draft)
    print(f"  선택된 초안: {draft.get('name')!r} (device_names={draft.get('device_names')})")

    run_dir = args.input.parent
    # cli_m2.py 가 만든 실행 폴더명("<날짜>_<제목슬러그>")에서 제목 슬러그만 다시 뽑아
    # log_prefix 로 쓴다(M2 검색 로그와 파일이 섞이지 않도록 "_m4" 를 붙인다).
    title_slug = re.sub(r"^\d{8}_", "", run_dir.name) or "run"
    log_prefix = f"{title_slug}_m4"

    # m3.json 은 module0/m1/m2 원본을 담지 않는다(m2.json 부터 이미 그렇다 — 사용자 요청) —
    # 있으면(구버전 파일과의 하위호환) 쓰고, 없으면 빈 dict.
    result = run_m4(data.get("module0") or {}, data.get("m1") or {}, data.get("m2") or {},
                    data["context"], data["creative_problem"], data["devices"], draft,
                    concept_line=data.get("concept_line", ""), ad_length=data.get("ad_length", "15초"),
                    backend=args.llm_backend, log_prefix=log_prefix, log_dir=str(run_dir))

    out_path = run_dir / "m4.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {out_path}")
    print(f"  컷 {len(result['scenes'])}개, 사용 장치 {len(result['devices_applied'])}개")


if __name__ == "__main__":
    main()
