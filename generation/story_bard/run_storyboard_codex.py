#!/usr/bin/env python3
"""Run Codex non-interactively to complete and render an HTML storyboard."""

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
            "HTML을 Codex에 전달해 완성 HTML, PNG, 생성 에셋, 참고자료, ZIP을 생성합니다."
        )
    )
    parser.add_argument(
        "--input_html",
        required=True,
        type=Path,
        help="입력 HTML 파일 경로",
    )
    parser.add_argument(
        "--output_dir",
        required=True,
        type=Path,
        help="완성 결과를 저장할 폴더",
    )
    parser.add_argument(
        "--refernece_dir",
        "--reference_dir",
        dest="reference_dir",
        type=Path,
        help=(
            "Product reference image directory. Both --refernece_dir and the "
            "correctly spelled --reference_dir are supported."
        ),
    )
    parser.add_argument(
        "--model",
        help="Codex 실행에 사용할 모델(생략하면 현재 Codex 설정 사용)",
    )
    parser.add_argument(
        "--codex_bin",
        help="Codex 실행 파일 경로 또는 명령 이름(생략하면 자동 탐색)",
    )
    parser.add_argument(
        "--extra_instruction",
        default="",
        help="기본 작업 프롬프트 뒤에 추가할 지시사항",
    )
    parser.add_argument(
        "--keep_session",
        action="store_true",
        help="Codex 세션 기록을 유지합니다(기본값은 ephemeral 실행).",
    )
    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="Codex를 실행하지 않고 명령과 프롬프트만 출력합니다.",
    )
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

    candidates = (
        ("codex.cmd", "codex.exe", "codex")
        if os.name == "nt"
        else ("codex",)
    )
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved

    raise FileNotFoundError(
        "Codex CLI를 찾을 수 없습니다. Codex CLI를 설치하고 로그인한 뒤 다시 실행하세요."
    )


def build_prompt(
    input_html: Path,
    output_dir: Path,
    reference_dir: Path | None,
    extra: str,
) -> str:
    extra_block = ""
    if extra.strip():
        extra_block = f"\n\n추가 사용자 지시사항:\n{extra.strip()}"

    reference_block = ""
    if reference_dir is not None:
        reference_block = f"""

USER-SUPPLIED PRODUCT REFERENCES
- Product reference directory: {reference_dir}
- Inspect this directory before browsing or generating product visuals. Treat
  usable files as the primary factual references for product shape, materials,
  proportions, colors, UI, and supplied brand marks.
- Do not modify or overwrite the source files.
- Copy every reference actually inspected or used into
  {output_dir / "references" / "user-supplied"} with recognizable filenames.
- Record every copied file in {output_dir / "references" / "sources.json"}.
  Set asset_type to "user-supplied-reference", source_url to the original
  absolute local path, local_path relative to the output directory, and explain
  whether it was inserted directly or used only as a visual reference.
- Prefer supplied factual product images over inventing a conflicting product.
  Browse for more factual material only when the supplied references do not
  cover a required view.
"""

    layout_tool = Path(__file__).resolve().with_name("storyboard_image_layout.py")
    layout_instruction = f"""

MANDATORY ADAPTIVE IMAGE LAYOUT PASS
- Do not derive final asset ratios from a placeholder's initial min-height.
- Keep uncropped master images and create {output_dir / "image-layout.json"} with
  an "assets" array. Each item needs output, source (except SVG), and category.
  Categories: character, character-detail, product, product-use, environment,
  storyboard, lighting.
- After inserting every image, run:
  python "{layout_tool}" --html "{output_dir / "completed.html"}" --manifest "{output_dir / "image-layout.json"}" --report "{output_dir / "image-layout-report.json"}"
- This pass uses a neutral solid background, contains the complete source in a
  safe area without any blurred duplicate, and makes each HTML slot follow the asset ratio so grid rows grow
  automatically. Treat a nonzero exit as a build failure and fix it.
- Render only after the pass. Verify complete head outlines, faces, hands, product
  silhouettes, UI bezels, and important scene elements. Never restore the
  placeholder's old fixed-height ratio.
"""

    return f"""\
{layout_instruction}
{reference_block}
아래 HTML 파일을 완성된 비주얼 산출물로 변환하라.

입력 HTML: {input_html}
출력 디렉터리: {output_dir}

작업 요구사항:
1. 입력 HTML을 먼저 읽고 구조, 목적, 레이아웃, 이미지 슬롯, 배경 이미지 자리,
   스토리보드 패널과 시각적 단서를 분석한다.
   작업 시작 시 이미지가 필요한 모든 슬롯의 총 개수를 동적으로 세고, 각 슬롯의
   섹션·순서·용도 목록을 만든다. 28개처럼 고정된 개수를 가정하지 않는다.
2. 입력 파일은 수정하지 않는다. 원본의 문구, 위계, 레이아웃과 브랜드 방향을
   보존한다.
3. 필요한 이미지 계획을 세운 뒤 사용 가능한 이미지 생성 기능을 이용해 실제
   이미지를 만든다. 슬롯이 많으면 캐릭터, 제품/UI, 세트/배경, 스토리보드처럼
   목적별 시트로 묶어 생성한 다음 필요한 영역을 크롭하거나 재사용한다.
   먼저 브라우저 또는 HTML/CSS 분석으로 각 슬롯의 실제 렌더링 가로세로비를
   측정하고 이미지 계획에 기록한다. 시트 전체를 CSS에서 확대하거나
   background-position/left/top으로 이동해 슬롯에서 잘라 보여주지 않는다.
   시트의 각 칸을 경계와 거터에 맞춰 실제 개별 이미지 파일로 정확히 분리한다.
   분리한 파일은 해당 슬롯 비율에서 object-fit: cover로 표시해도 얼굴, 손,
   제품, UI 화면 같은 핵심 피사체가 모두 안전 영역 안에 남도록 구도를 잡는다.
   필요하면 개별 파일을 슬롯 비율에 맞게 피사체 중심으로 다시 크롭하거나,
   주변 배경을 확장한 slot-ready 파생 파일을 만든다. 단순 균등분할 결과를
   검수 없이 바로 사용하지 않는다.
4. 사람이 등장하는 모든 생성 이미지에서 얼굴 전체를 강한 블러로 정확히
   익명 처리한다. 작은 얼굴이나 측면 얼굴도 식별할 수 없어야 한다.
5. 실제 제품, 공식 앱 화면, 로고 같은 사실 기반 자산을 임의로 발명하지 않는다.
   필요한 경우 공식 사이트, 공식 앱스토어, 제조사/서비스 운영사의 공개 페이지를
   우선 조사한다. 로그인, 유료 접근, CAPTCHA 또는 접근 제한을 우회하지 않는다.
6. 조사 과정에서 모델이 실제로 참고한 제품 이미지, 앱 스크린샷, 웹페이지
   캡처와 기타 시각 자료를 {output_dir / "references"} 아래에 원본 형식을
   가능한 한 유지해 저장한다. 생성 이미지와 크롭 결과는 references에 넣지
   않는다. 참고자료 파일명은 출처와 내용을 알아볼 수 있게 작성한다.
7. {output_dir / "references" / "sources.json"}에 모든 참고자료의 메타데이터를
   JSON 배열로 기록한다. local_path는 출력 디렉터리 기준 상대 경로로 작성한다.
   각 항목은 최소한 local_path, source_url, page_title,
   publisher, retrieved_at, asset_type, used_for, usage_note 필드를 포함해야 한다.
   라이선스가 명확하지 않은 자료는 usage_note에 "reference-only"라고 표시하고
   최종 HTML에 직접 복제하지 않는다. 유효한 자료를 확보하지 못했더라도
   references 폴더와 빈 배열([])의 sources.json은 생성한다.
8. 신뢰할 수 있는 공식 자료를 확보하지 못하면 브랜드 표식이 없는 비공식
   콘셉트 이미지로 재구성하고 정확한 문구는 HTML 텍스트로 유지한다.
9. 생성한 파일은 {output_dir / "assets"} 아래에 명확한 이름으로 저장하고,
   완성 HTML은 상대 경로로 에셋을 참조하며 의미 있는 alt 속성을 포함해야 한다.
   이미지 슬롯은 아래 기준 구현과 동등한 방식으로 자동 비율 맞춤을 적용한다.
   기존 클래스 구조가 있으면 이름은 유지하되 동작은 동일하게 구현한다.

   .slot.has-image {{
     padding: 0;
     overflow: hidden;
     border-style: solid;
     background: #e9e9e5;
   }}
   .slot.has-image img {{
     display: block;
     width: 100%;
     height: 100%;
     min-height: inherit;
     object-fit: cover;
     object-position: center;
   }}

   각 슬롯에는 시트 원본이 아니라 분리된 개별 이미지 파일 하나를 삽입한다.
   cover로 잘리는 주변 배경은 허용하지만 얼굴 전체, 머리 윤곽, 손동작, 제품
   외곽선, 화면 UI와 장면 이해에 필요한 요소는 절대 잘리면 안 된다. 핵심 요소가
   잘리면 contain으로 임시 회피하지 말고, 개별 에셋의 캔버스/크롭/안전 여백을
   조정하거나 슬롯별 object-position을 미세 조정해 꽉 찬 레이아웃과 가독성을
   함께 확보한다. 빈 레터박스가 과도하게 생기는 contain 방식은 기본값으로
   사용하지 않는다.
10. 브라우저 렌더링을 우선 사용해 이미지 로딩, 크기, 잘림, 오버플로, 겹침,
   텍스트 충돌을 검수한다. 브라우저 캡처가 불가능하면 같은 에셋과 레이아웃을
   사용한 미리보기 PNG를 만든다. 데스크톱 기준 전체 페이지 스크린샷뿐 아니라
   모든 이미지 슬롯을 개별적으로 확인한다. 슬롯이 빈 공간 없이 자연스럽게
   채워졌는지, 이미지 비율이 왜곡되지 않았는지, 피사체의 머리, 얼굴, 손,
   제품 모서리, UI 화면과 주요 배경 요소가 모두 보이는지 검사한다. 하나라도
   잘리거나 늘어나거나 과도한 레터박스가 생기면 CSS만 억지로 바꾸지 말고
   slot-ready 개별 에셋의 비율과 안전 구도를 수정한 뒤 다시 렌더링한다.
   최종 HTML의 삽입 이미지 수가 작업 시작 시 센 이미지 슬롯 수와 정확히 같은지
   비교한다. 선택적 슬롯을 비워야 하는 명확한 근거가 없는 한 플레이스홀더를
   하나도 남기지 않는다. 개수가 다르면 누락 슬롯을 찾아 채우고 다시 검증한다.
11. 질문이나 확인을 기다리지 말고 합리적인 가정으로 끝까지 수행한다. 같은
   실패 경로를 반복하지 말고 실용적인 대체 방법을 사용한다.

반드시 다음 경로에 최종 파일을 생성하라:
- {output_dir / "completed.html"}
- {output_dir / "completed.png"}
- {output_dir / "assets"}
- {output_dir / "references"}
- {output_dir / "references" / "sources.json"}
- {output_dir / "completed-package.zip"}

ZIP에는 completed.html, completed.png, HTML이 참조하는 모든 에셋, references
폴더와 sources.json이 들어 있어야 한다. 완료 전에 모든 필수 결과물이 실제로
존재하고, HTML의 상대 이미지 경로와 sources.json의 local_path가 모두 유효한지
검사하라. 최종 응답에는 생성 이미지와 저장한 외부 참고자료의 구분, 렌더링 방식,
가정과 제한사항을 간단히 기록하라.{extra_block}
"""


def build_command(
    codex_bin: str,
    output_dir: Path,
    last_message: Path,
    model: str | None,
    keep_session: bool,
) -> list[str]:
    command = [
        codex_bin,
        "exec",
        "--sandbox",
        "workspace-write",
        "--skip-git-repo-check",
        "--color",
        "never",
        "--cd",
        str(output_dir),
        "--output-last-message",
        str(last_message),
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
            # Windows PowerShell 5의 Set-Content -Encoding UTF8은 BOM을 추가한다.
            # utf-8-sig는 BOM 포함/미포함 JSON을 모두 처리한다.
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
                        issues.append(
                            f"sources.json[{index}] 경로가 references 밖을 가리킴: "
                            f"{local_path}"
                        )
                    else:
                        if not reference_path.is_file():
                            issues.append(
                                f"sources.json[{index}] 참고자료 파일 없음: {local_path}"
                            )

    package_path = output_dir / "completed-package.zip"
    if package_path.is_file():
        try:
            with zipfile.ZipFile(package_path) as package:
                names = {name.replace("\\", "/") for name in package.namelist()}
        except (OSError, zipfile.BadZipFile) as exc:
            issues.append(f"ZIP 파일을 읽을 수 없음: {exc}")
        else:
            for required in (
                "completed.html",
                "completed.png",
                "references/sources.json",
            ):
                if required not in names:
                    issues.append(f"ZIP에 필수 파일 없음: {required}")

    return issues


def main() -> int:
    args = parse_args()
    input_html = args.input_html.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    reference_dir = (
        args.reference_dir.expanduser().resolve()
        if args.reference_dir is not None
        else None
    )

    if not input_html.is_file():
        print(f"오류: 입력 파일을 찾을 수 없습니다: {input_html}", file=sys.stderr)
        return 2
    if input_html.suffix.lower() not in {".html", ".htm"}:
        print(f"오류: HTML 파일이 아닙니다: {input_html}", file=sys.stderr)
        return 2

    if reference_dir is not None and not reference_dir.is_dir():
        print(
            f"오류: 제품 참조 이미지 폴더를 찾을 수 없습니다: {reference_dir}",
            file=sys.stderr,
        )
        return 2

    try:
        codex_bin = find_codex(args.codex_bin)
    except FileNotFoundError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2

    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    last_message = output_dir / "codex-last-message.txt"
    prompt = build_prompt(
        input_html,
        output_dir,
        reference_dir,
        args.extra_instruction,
    )
    command = build_command(
        codex_bin=codex_bin,
        output_dir=output_dir,
        last_message=last_message,
        model=args.model,
        keep_session=args.keep_session,
    )

    if args.dry_run:
        print("Command:")
        print(subprocess.list2cmdline(command))
        print("\nPrompt:")
        print(prompt)
        return 0

    print(f"[storyboard] input : {input_html}", flush=True)
    print(f"[storyboard] output: {output_dir}", flush=True)
    if reference_dir is not None:
        print(f"[storyboard] references: {reference_dir}", flush=True)
    print("[storyboard] Codex 실행을 시작합니다.", flush=True)

    try:
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            encoding="utf-8",
            cwd=output_dir,
            check=False,
        )
    except KeyboardInterrupt:
        print("\n[storyboard] 사용자에 의해 중단되었습니다.", file=sys.stderr)
        return 130
    except OSError as exc:
        print(f"[storyboard] Codex 실행 실패: {exc}", file=sys.stderr)
        return 1

    if completed.returncode != 0:
        print(
            f"[storyboard] Codex가 종료 코드 {completed.returncode}로 실패했습니다.",
            file=sys.stderr,
        )
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
    print(f"  - {last_message}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
