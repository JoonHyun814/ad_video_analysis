"""retrieval_pipeline CLI — M3(M2 장치 조합 → 러프 시나리오 초안 5개 생성).

M2(cli_m2.py) 다음 단계. m2.json(context+creative_problem+devices 8개)을 읽어, LLM이 그중
2~4개씩 조합한 서로 다른 방향의 러프 시나리오 초안 5개를 만든다(도구 호출 없음 — 장치 자체의
근거는 이미 M2에서 끝난 일이다, scenario_draft.py). 완성된 대본이 아니라 여러 방향을 빠르게
비교하기 위한 스케치다(사용자 요청 — "m2의 device를 2~4개정도 조합해서 러프한 시나리오를
5개정도 생성").

M4(scenario_generation.py, 풀 프로덕션 시나리오 1개 완성)와는 독립적인 별개 경로다 — 지금은
M4가 이 초안을 거치지 않고 m2.json을 직접 받는다. 이 초안 5개 중 하나를 골라 M4로 넘기는
배선은 아직 없다(다음 요청에서 다룬다 — "한단계씩 개발").

새 날짜 폴더를 만들지 않고 --input 파일과 같은 디렉터리에 m3.json으로 저장한다(cli_m4.py와
같은 관례).

사용법:
    python -m generation.retrieval_pipeline.cli_m3 \\
        --input output/retrieval_pipeline/<날짜>_<제목>/m2.json \\
        [--concept "..."] [--llm_backend cli|api]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from generation.retrieval_pipeline.pipeline import run_m3


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="retrieval_pipeline M3 (M2 장치 조합 → 러프 시나리오 초안 5개)")
    p.add_argument("--input", type=Path, required=True,
                   help="m2.json 경로(context/creative_problem/devices 포함)")
    p.add_argument("--concept", default=None,
                   help="한 줄 크리에이티브 원칙 재지정(선택 — 안 주면 m2.json의 concept_line을 그대로 쓴다)")
    p.add_argument("--llm_backend", default="cli", choices=("cli", "api"),
                   help="cli: claude -p(기본) | api: Anthropic API 직접 호출")
    return p


def main() -> None:
    args = _build_parser().parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    if data.get("error"):
        raise SystemExit(f"[오류] 입력 파일에 error 있음 — M2 부터 다시 확인: {data['error']}")
    if not data.get("devices"):
        raise SystemExit("[오류] 입력 파일에 devices 가 없음 — cli_m2.py 를 먼저 실행하세요.")

    run_dir = args.input.parent
    # cli_m2.py 가 만든 실행 폴더명("<날짜>_<제목슬러그>")에서 제목 슬러그만 다시 뽑아
    # log_prefix 로 쓴다(도구를 안 쓰므로 실제 로그 파일은 안 생기지만, tool_chat.run() 관례를
    # 그대로 따른다 — M4 의 "_m4" 접미사와 같은 이유로 "_m3"를 붙인다).
    title_slug = re.sub(r"^\d{8}_", "", run_dir.name) or "run"
    log_prefix = f"{title_slug}_m3"

    concept_line = args.concept if args.concept is not None else data.get("concept_line", "")
    result = run_m3(data["context"], data["creative_problem"], data["devices"],
                    concept_line=concept_line, ad_length=data.get("ad_length", "15초"),
                    backend=args.llm_backend, log_prefix=log_prefix, log_dir=str(run_dir))

    out_path = run_dir / "m3.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {out_path}")
    print(f"  시나리오 초안 {len(result['drafts'])}개 생성됨")


if __name__ == "__main__":
    main()
