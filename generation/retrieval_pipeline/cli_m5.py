"""retrieval_pipeline CLI — M5(M4 시나리오 → 스토리보드 이미지 슬롯 계획 + Seedance 영상
모션 프롬프트).

M4(cli_m4.py) 다음 단계. m4.json(시나리오: title/brand/concept/narrative/cast/scenes/
key_messages/production_notes)을 읽어 두 파일을 만든다:
  - m5.json         StoryboardShotPlan(인물 3슬롯×인원수/제품 소싱 브리프/Environment/
                     컷별 키프레임+Seedance 모션 프롬프트) + 체이닝용 상위 단계 필드
  - storyboard.html generation/AITIVE_스토리보드_틀.html 을 이 프로젝트의 실제 인물 수·
                     컷 수에 맞춰 찍어낸 빈 이미지 슬롯 HTML(storyboard_template.py)

이 단계는 이미지를 생성하지 않는다 — storyboard.html + m5.json 을 실제로 채우는 건 별도
실행하는 storyboard_codex.py(Codex CLI)의 몫이다(사용자 요청 — "codex를 이용하여서 구현").
--input 파일과 같은 폴더에 저장한다(파이프라인 관례).

사용법:
    python -m generation.retrieval_pipeline.cli_m5 \\
        --input output/retrieval_pipeline/<날짜>_<제목>/m4.json [--llm_backend cli|api]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from generation.retrieval_pipeline import storyboard_generation, storyboard_template
from generation.retrieval_pipeline.pipeline import run_m5


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="retrieval_pipeline M5(M4 시나리오 → 스토리보드 이미지 슬롯 계획 + Seedance 프롬프트)")
    p.add_argument("--input", type=Path, required=True,
                   help="m4.json 경로(module0/m1/m2/context/creative_problem/devices + 시나리오 필드 포함)")
    p.add_argument("--llm_backend", default="cli", choices=("cli", "api"),
                   help="cli: claude -p(기본) | api: Anthropic API 직접 호출")
    return p


def main() -> None:
    args = _build_parser().parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    if data.get("error"):
        raise SystemExit(f"[오류] 입력 파일에 error 있음 — M4 부터 다시 확인: {data['error']}")
    if not data.get("scenes"):
        raise SystemExit("[오류] 입력 파일에 scenes 가 없음 — cli_m4.py 를 먼저 실행하세요.")

    scenario = storyboard_generation.scenario_fields(data)

    run_dir = args.input.parent
    title_slug = re.sub(r"^\d{8}_", "", run_dir.name) or "run"
    log_prefix = f"{title_slug}_m5"

    result = run_m5(data["module0"], data["m1"], data["m2"], data["context"],
                    data["creative_problem"], data["devices"], scenario,
                    backend=args.llm_backend, log_prefix=log_prefix, log_dir=str(run_dir))

    out_path = run_dir / "m5.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    doc_title = f"{scenario.get('brand', '')} · {scenario.get('title', '')}".strip(" ·") or "스토리보드"
    html = storyboard_template.render_from_shot_plan(scenario, doc_title=doc_title)
    html_path = run_dir / "storyboard.html"
    html_path.write_text(html, encoding="utf-8")

    print(f"  저장: {out_path}")
    print(f"  저장: {html_path}")
    print(f"  인물 {len(result['characters'])}명, 제품 소싱 브리프 {len(result['product']['shot_briefs'])}개, "
          f"컷 {len(result['cuts'])}개 계획 완성")
    print("  다음 단계: storyboard_codex.py 로 실제 이미지를 생성/삽입하세요"
          "(python -m generation.retrieval_pipeline.storyboard_codex --help).")


if __name__ == "__main__":
    main()
