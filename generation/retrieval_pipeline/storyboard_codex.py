#!/usr/bin/env python3
"""Run Codex non-interactively to fill the M5 storyboard's image slots and render it.

Adapted (not imported) from C:\\Analysis_workspace\\ad_video_analysis\\story_board\\
run_storyboard_codex.py into this pipeline (user request — copy that project's Codex-driving
approach independently rather than depending on it). One deliberate difference from the
original:

1. The original had Codex *infer* what each slot should contain by reading prose already
   embedded in the input HTML. Our storyboard.html (storyboard_template.py) intentionally
   carries almost no text — each slot has only a one-line caption (e.g. "캐릭터1 · 정면",
   "제품 · 컷2", "컷5"). The actual generation/sourcing instructions live in m5.json
   (StoryboardShotPlan, schemas.py) instead. This script loads that plan and embeds the
   full per-slot instruction directly in the Codex prompt, keyed by the same caption text
   used in the HTML, so Codex does not need to guess.

Faces ARE strongly blurred in every generated character/person image (user request, matching
the original story_board policy) — this storyboard is a reviewable deliverable, not a raw
identity-anchor asset. If a later Seedance step needs unblurred reference images, that is a
separate concern for whatever generates that step's inputs, not this script.

Product images are sourced, not invented (user request): Codex is told to prefer files in
--reference_dir (user-supplied product photos) and to browse official sources for any product
shot_brief the supplied references don't cover, falling back to a brand-mark-free concept
reconstruction only when no factual source exists.

This script does not call Seedance and does not write video motion prompts into the image
pipeline — it writes them straight from m5.json into <output_dir>/seedance_prompts.json (pure
Python, no Codex involvement) so they travel alongside the finished images for a later step.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


REQUIRED_OUTPUTS = (
    "completed.html",
    "completed.png",
    "completed-package.zip",
    "assets",
    "references",
    "references/sources.json",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "m5.json 촬영 계획대로 storyboard.html의 이미지 슬롯을 Codex로 채우고 "
            "완성 HTML/PNG/에셋/참고자료/ZIP을 생성합니다."
        )
    )
    parser.add_argument(
        "--input_html", required=True, type=Path,
        help="cli_m5.py가 만든 storyboard.html 경로",
    )
    parser.add_argument(
        "--shot_plan", required=True, type=Path,
        help="cli_m5.py가 만든 m5.json 경로(StoryboardShotPlan 필드 포함)",
    )
    parser.add_argument(
        "--output_dir", required=True, type=Path,
        help="완성 결과를 저장할 폴더",
    )
    parser.add_argument(
        "--refernece_dir", "--reference_dir", dest="reference_dir", type=Path,
        help="사용자가 공급한 제품 참조 사진 폴더(선택) — 두 철자 모두 지원",
    )
    parser.add_argument("--model", help="Codex 실행에 사용할 모델(생략하면 현재 Codex 설정 사용)")
    parser.add_argument("--codex_bin", help="Codex 실행 파일 경로 또는 명령 이름(생략하면 자동 탐색)")
    parser.add_argument(
        "--sandbox", default="danger-full-access",
        choices=("workspace-write", "danger-full-access", "read-only"),
        help=(
            "codex exec --sandbox 값. 기본값 danger-full-access — 이 환경(Windows)에서 "
            "workspace-write 는 config.toml 의 windows.sandbox 값에 따라 실행 자체가 막힌다: "
            "elevated 는 사전에 `codex sandbox setup --elevated` 로 별도 헬퍼를 띄워두지 않으면 "
            "'timed out ... connecting runner pipe-in' 으로 멈추고, unelevated(restricted-token) "
            "는 workspace-write 가 요구하는 다중 쓰기 루트(workdir+tmp)를 지원하지 않아 "
            "'refusing to run unsandboxed' 로 모든 명령이 거부된다(둘 다 이 스크립트로 직접 "
            "재현·확인함). `codex sandbox setup --elevated` 를 완료했다면 --sandbox "
            "workspace-write 로 다시 전환해 OS 수준 격리를 쓸 수 있다 — danger-full-access 는 "
            "그 격리 없이 Codex에게 전체 파일 접근 권한을 준다(EXTREMELY DANGEROUS, Codex 자체 "
            "경고 문구)."
        ),
    )
    parser.add_argument("--extra_instruction", default="", help="기본 작업 프롬프트 뒤에 추가할 지시사항")
    parser.add_argument("--keep_session", action="store_true", help="Codex 세션 기록을 유지합니다(기본값은 ephemeral 실행)")
    parser.add_argument("--dry_run", action="store_true", help="Codex를 실행하지 않고 명령과 프롬프트만 출력합니다")
    return parser.parse_args()


def find_codex(explicit: str | None) -> str:
    if explicit:
        explicit_path = Path(explicit).expanduser()
        if explicit_path.exists():
            return str(explicit_path.resolve())
        resolved = shutil.which(explicit)
        if resolved:
            return resolved
        raise FileNotFoundError(f"Codex 실행 파일을 찾을 수 없습니다: {explicit}")

    candidates = ("codex.cmd", "codex.exe", "codex") if os.name == "nt" else ("codex",)
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise FileNotFoundError("Codex CLI를 찾을 수 없습니다. Codex CLI를 설치하고 로그인한 뒤 다시 실행하세요.")


def _slot_instructions(plan: dict) -> str:
    """m5.json(StoryboardShotPlan)을 '슬롯 캡션 -> 지시문' 목록 텍스트로 펼친다 — storyboard.html
    의 <div class="slot"><span>캡션</span></div> 과 캡션 문자열로 1:1 매칭된다."""
    lines: list[str] = []

    lines.append("### 인물 슬롯 — 이미지 생성 (실존하지 않는 콘셉트 캐스팅)")
    for character in plan.get("characters", []):
        cid = character.get("id", "")
        lines.append(f'- "{cid} · 정면" [생성]: {character.get("front_prompt", "")}')
        lines.append(f'- "{cid} · 측면" [생성]: {character.get("profile_prompt", "")}')
        lines.append(f'- "{cid} · 의상 착용" [생성]: {character.get("costume_prompt", "")}')

    product = plan.get("product", {})
    lines.append("\n### 제품 슬롯 — 소싱 우선 (실물, 지어내지 않는다)")
    for i, brief in enumerate(product.get("shot_briefs", []), start=1):
        lines.append(f'- "제품 · 컷{i}" [소싱]: {brief}')
    lines.append(f'- "제품 · 로고" [소싱]: {product.get("logo_brief", "")}')

    environment = plan.get("environment", {})
    lines.append("\n### Environment 슬롯 — 이미지 생성")
    lines.append(f'- "Environment" [생성]: {environment.get("prompt", "")}')

    lines.append("\n### 컷별 슬롯 — 이미지 생성 (키프레임 정지 이미지만; 모션 텍스트는 다루지 않음)")
    for cut in plan.get("cuts", []):
        idx = cut.get("cut_index", "")
        lines.append(f'- "컷{idx}" [생성]: {cut.get("keyframe_image_prompt", "")}')

    return "\n".join(lines)


def _product_facts_block(plan: dict) -> str:
    """m5.json은 pipeline.run_m5()가 만든 전체 dict라 module0(제품 원본 사실)를 그대로 담고
    있다 — 제품 슬롯 [소싱] 지시문이 참조하는 "제품 사실" 섹션을 여기서 뽑아 만든다."""
    module0 = plan.get("module0") or {}
    if not module0:
        return "(module0 정보 없음 — shot_plan 이 pipeline.run_m5() 전체 출력이 아닐 수 있다)"
    facts = "\n".join(f"  - {f}" for f in (module0.get("facts") or [])[:6])
    usp = "\n".join(
        f"  - {(u.get('text', '') if isinstance(u, dict) else u)}"
        for u in (module0.get("usp_candidates") or [])[:5]
    )
    return (
        f"- 제품명: {module0.get('product_name', '')}\n"
        f"- 카테고리: {module0.get('category', '')}\n"
        f"- 대표 제품 이미지 URL(1차 참고): {module0.get('product_image_url', '') or '(없음)'}\n"
        f"- 제품 사실:\n{facts or '  (없음)'}\n"
        f"- USP 후보:\n{usp or '  (없음)'}"
    )


def build_prompt(input_html: Path, shot_plan: Path, output_dir: Path,
                 reference_dir: Path | None, extra: str) -> str:
    plan = json.loads(shot_plan.read_text(encoding="utf-8"))
    slot_instructions = _slot_instructions(plan)
    product_facts = _product_facts_block(plan)

    extra_block = f"\n\n추가 사용자 지시사항:\n{extra.strip()}" if extra.strip() else ""

    reference_block = ""
    if reference_dir is not None:
        reference_block = f"""

USER-SUPPLIED PRODUCT REFERENCES
- Product reference directory: {reference_dir}
- Inspect this directory FIRST for every "[소싱]" 제품 슬롯. Treat usable files as the primary
  factual reference for shape, materials, proportions, colors, UI, and supplied brand marks.
- Do not modify or overwrite the source files.
- Copy every reference actually inspected or used into
  {output_dir / "references" / "user-supplied"} with recognizable filenames.
- Record every copied file in {output_dir / "references" / "sources.json"} with
  asset_type "user-supplied-reference".
"""

    layout_tool = Path(__file__).resolve().with_name("storyboard_image_layout.py")

    return f"""\
아래 storyboard.html 은 이미지 슬롯만 있는 빈 틀이다(캡션 하나가 텍스트의 전부). 각 슬롯에
무엇을 채울지는 아래 "슬롯별 지시문"에 캡션별로 이미 정해져 있다 — HTML의 문구를 해석해서
추측하지 말고, 이 지시문을 그대로 따르라.

입력 HTML: {input_html}
출력 디렉터리: {output_dir}

## 슬롯 구조
- 모든 이미지 슬롯은 `<div class="slot ...">` 안에 `<span>캡션</span>` 하나만 들어 있다.
- 슬롯 캡션과 아래 지시문의 첫 따옴표 문자열이 정확히 일치하는 슬롯에 그 지시문으로 만든
  이미지를 삽입하라. 슬롯 총 개수와 아래 지시문 개수는 정확히 같다 — 하나도 비우지 마라.

## 제품 사실 (module0 — [소싱] 슬롯의 근거)
{product_facts}

## 슬롯별 지시문
[생성] = 이미지 생성 모델로 새로 그린다. [소싱] = 위 "제품 사실"과 참조 폴더(있다면)에서
실제 사진을 찾아 배치하고, 부족한 각도만 공식 소스를 웹에서 조사해 보완한다 — 존재하지
않는 디테일을 지어내지 않는다.

{slot_instructions}
{reference_block}
## 실행 원칙
1. 입력 HTML은 수정하지 않는다(구조·클래스·캡션 보존). 이미지만 슬롯 안에 삽입한다.
2. **사람이 등장하는 모든 이미지에서 얼굴 전체를 강한 블러로 정확히 익명 처리하라.**
   인물 슬롯(정면/측면/의상 착용)뿐 아니라 컷별 슬롯에 인물의 얼굴이 나오는 경우도
   동일하게 적용한다. 작은 얼굴·측면 얼굴·부분적으로만 보이는 얼굴(턱·입 등)도 식별할 수
   없어야 한다 — 눈·코·입 윤곽이 전혀 구분되지 않을 정도로 강하게 블러 처리하고, 헤어라인
   부터 턱까지 빠짐없이 덮되 목·쇄골 같은 얼굴 밖 부위(특히 이 제품이 주얼리라면 착용
   부위)는 가리지 마라.
3. 같은 인물 ID(예: "캐릭터1")의 정면/측면/의상 착용 세 슬롯은 얼굴을 뺀 나머지(헤어·체형·
   인상 윤곽·의상)가 반드시 같은 사람으로 보여야 한다 — 슬롯마다 달라지면 안 된다.
4. 제품 로고를 새로 만들어내거나 왜곡하지 마라. 신뢰할 수 있는 실물 자료를 확보하지
   못하면 브랜드 표식 없는 비공식 콘셉트 이미지로 재구성하고, usage_note에
   "reference-only" 또는 "reconstructed"라고 적어라.
5. 조사 과정에서 실제로 참고한 제품 이미지·웹페이지 캡처는
   {output_dir / "references"} 아래에 원본 형식을 유지해 저장하고,
   {output_dir / "references" / "sources.json"} 에 local_path, source_url, page_title,
   publisher, retrieved_at, asset_type, used_for, usage_note 를 포함한 메타데이터를
   JSON 배열로 기록하라(참고자료가 하나도 없어도 references 폴더와 빈 배열 sources.json은
   생성한다). 로그인·유료 접근·CAPTCHA·접근 제한을 우회하지 않는다.
6. 생성/크롭한 파일은 {output_dir / "assets"} 아래 명확한 이름으로 저장하고, alt 속성에
   해당 슬롯 캡션을 반영하라.
7. MANDATORY ADAPTIVE IMAGE LAYOUT PASS — 슬롯의 초기 min-height 비율로 최종 에셋 비율을
   정하지 마라. 원본(무크롭) 마스터 이미지를 보존하고 {output_dir / "image-layout.json"} 에
   "assets" 배열(각 항목 output/source(SVG 제외)/category — character, character-detail,
   product, environment, storyboard 중 하나)을 작성한 뒤 실행하라:
   python "{layout_tool}" --html "{output_dir / "completed.html"}" --manifest "{output_dir / "image-layout.json"}" --report "{output_dir / "image-layout-report.json"}"
   중립 단색 배경에 원본 전체가 안전 영역(92%) 안에 들어가는 방식이며, 슬롯이 에셋 비율을
   그대로 따르게 만든다. 종료 코드가 0이 아니면 빌드 실패로 간주하고 고쳐라. 렌더링은 이
   패스 이후에만 한다.
8. 브라우저 렌더링(또는 동등한 캡처)으로 이미지 로딩·크기·잘림·오버플로·겹침을 검수한다.
   얼굴 전체, 손, 제품 모서리, 로고, 배경 핵심 요소가 모두 안전 영역 안에 있는지 슬롯마다
   확인한다. 최종 삽입 이미지 수가 슬롯 총 개수와 정확히 같은지 비교하고, 다르면 누락 슬롯을
   채운 뒤 다시 검증한다.
9. 질문이나 확인을 기다리지 말고 합리적인 가정으로 끝까지 수행한다.

반드시 다음 경로에 최종 파일을 생성하라:
- {output_dir / "completed.html"}
- {output_dir / "completed.png"}
- {output_dir / "assets"}
- {output_dir / "references"}
- {output_dir / "references" / "sources.json"}
- {output_dir / "completed-package.zip"}

ZIP에는 completed.html, completed.png, HTML이 참조하는 모든 에셋, references 폴더와
sources.json이 들어 있어야 한다. 완료 전에 모든 필수 결과물이 실제로 존재하고, HTML의
상대 이미지 경로와 sources.json의 local_path가 모두 유효한지 검사하라. 최종 응답에는
생성 이미지와 저장한 외부 참고자료의 구분, 렌더링 방식, 가정과 제한사항을 간단히
기록하라.{extra_block}
"""


def write_seedance_prompts(shot_plan: Path, output_dir: Path) -> Path:
    """m5.json 의 cuts[].seedance_prompt 를 그대로 <output_dir>/seedance_prompts.json 에
    옮겨 적는다 — Codex는 이미지 슬롯만 다루고, 영상 모션 텍스트 프롬프트는 이 파이썬 코드가
    직접 복사한다(사용자 요청 — "필요한 이미지 정보는 스토리보드에 담고 텍스트 정보들은
    prompt에 적어줘": 이미지는 Codex가, 텍스트는 여기서 분리해서 낸다)."""
    plan = json.loads(shot_plan.read_text(encoding="utf-8"))
    prompts = [
        {"cut_index": cut.get("cut_index"), "seedance_prompt": cut.get("seedance_prompt", "")}
        for cut in plan.get("cuts", [])
    ]
    out_path = output_dir / "seedance_prompts.json"
    out_path.write_text(json.dumps(prompts, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def build_command(codex_bin: str, output_dir: Path, last_message: Path,
                  model: str | None, keep_session: bool, sandbox: str) -> list[str]:
    command = [
        codex_bin, "exec", "--sandbox", sandbox, "--skip-git-repo-check",
        "--color", "never", "--cd", str(output_dir),
        "--output-last-message", str(last_message),
    ]
    if not keep_session:
        command.append("--ephemeral")
    if model:
        command.extend(("--model", model))
    command.append("-")
    return command


def validate_outputs(output_dir: Path) -> list[str]:
    issues = [
        f"필수 결과 없음: {output_dir / relative}"
        for relative in REQUIRED_OUTPUTS
        if not (output_dir / relative).exists()
    ]

    manifest_path = output_dir / "references" / "sources.json"
    references_root = (output_dir / "references").resolve()
    if manifest_path.is_file():
        try:
            sources = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            issues.append(f"참고자료 manifest를 읽을 수 없음: {exc}")
        else:
            if not isinstance(sources, list):
                issues.append("references/sources.json의 최상위 값은 JSON 배열이어야 함")
            else:
                for index, source in enumerate(sources):
                    if not isinstance(source, dict):
                        issues.append(f"sources.json[{index}]가 객체가 아님")
                        continue
                    local_path = source.get("local_path")
                    if not isinstance(local_path, str) or not local_path.strip():
                        issues.append(f"sources.json[{index}].local_path가 비어 있음")
                        continue
                    reference_path = (output_dir / local_path).resolve()
                    try:
                        reference_path.relative_to(references_root)
                    except ValueError:
                        issues.append(f"sources.json[{index}] 경로가 references 밖을 가리킴: {local_path}")
                    else:
                        if not reference_path.is_file():
                            issues.append(f"sources.json[{index}] 참고자료 파일 없음: {local_path}")

    package_path = output_dir / "completed-package.zip"
    if package_path.is_file():
        try:
            with zipfile.ZipFile(package_path) as package:
                names = {name.replace("\\", "/") for name in package.namelist()}
        except (OSError, zipfile.BadZipFile) as exc:
            issues.append(f"ZIP 파일을 읽을 수 없음: {exc}")
        else:
            for required in ("completed.html", "completed.png", "references/sources.json"):
                if required not in names:
                    issues.append(f"ZIP에 필수 파일 없음: {required}")

    return issues


def main() -> int:
    try:  # Windows 콘솔 기본 코드페이지(cp949)가 한글 프롬프트의 특수문자(—, ' 등)를
        sys.stdout.reconfigure(encoding="utf-8")  # 인코딩하지 못해 --dry_run 출력이 죽는 것을 막는다.
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    args = parse_args()
    input_html = args.input_html.expanduser().resolve()
    shot_plan = args.shot_plan.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    reference_dir = args.reference_dir.expanduser().resolve() if args.reference_dir is not None else None

    if not input_html.is_file():
        print(f"오류: 입력 HTML을 찾을 수 없습니다: {input_html}", file=sys.stderr)
        return 2
    if not shot_plan.is_file():
        print(f"오류: 촬영 계획(m5.json)을 찾을 수 없습니다: {shot_plan}", file=sys.stderr)
        return 2
    if reference_dir is not None and not reference_dir.is_dir():
        print(f"오류: 제품 참조 이미지 폴더를 찾을 수 없습니다: {reference_dir}", file=sys.stderr)
        return 2

    try:
        codex_bin = find_codex(args.codex_bin)
    except FileNotFoundError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2

    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    if args.sandbox == "danger-full-access":
        print(
            "[storyboard] 경고: --sandbox danger-full-access — Codex가 OS 수준 격리 없이 전체 "
            "파일에 접근한다(이 환경의 workspace-write 가 막혀 있어 기본값으로 씀 — "
            "`codex sandbox setup --elevated` 완료 후 --sandbox workspace-write 로 전환 권장).",
            file=sys.stderr,
        )

    last_message = output_dir / "codex-last-message.txt"
    prompt = build_prompt(input_html, shot_plan, output_dir, reference_dir, args.extra_instruction)
    command = build_command(codex_bin, output_dir, last_message, args.model, args.keep_session, args.sandbox)

    if args.dry_run:
        print("Command:")
        print(subprocess.list2cmdline(command))
        print("\nPrompt:")
        print(prompt)
        return 0

    seedance_path = write_seedance_prompts(shot_plan, output_dir)

    print(f"[storyboard] input html : {input_html}", flush=True)
    print(f"[storyboard] shot plan  : {shot_plan}", flush=True)
    print(f"[storyboard] output     : {output_dir}", flush=True)
    print(f"[storyboard] seedance prompts written: {seedance_path}", flush=True)
    if reference_dir is not None:
        print(f"[storyboard] product references: {reference_dir}", flush=True)
    print("[storyboard] Codex 실행을 시작합니다.", flush=True)

    try:
        completed = subprocess.run(
            command, input=prompt, text=True, encoding="utf-8", cwd=output_dir, check=False,
        )
    except KeyboardInterrupt:
        print("\n[storyboard] 사용자에 의해 중단되었습니다.", file=sys.stderr)
        return 130
    except OSError as exc:
        print(f"[storyboard] Codex 실행 실패: {exc}", file=sys.stderr)
        return 1

    if completed.returncode != 0:
        print(f"[storyboard] Codex가 종료 코드 {completed.returncode}로 실패했습니다.", file=sys.stderr)
        return completed.returncode

    issues = validate_outputs(output_dir)
    if issues:
        print("[storyboard] Codex 실행은 끝났지만 결과 검증에 실패했습니다:", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        if last_message.exists():
            print(f"[storyboard] 마지막 응답: {last_message}", file=sys.stderr)
        return 3

    print("[storyboard] 완료:", flush=True)
    for relative in REQUIRED_OUTPUTS:
        print(f"  - {output_dir / relative}", flush=True)
    print(f"  - {seedance_path}", flush=True)
    print(f"  - {last_message}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
