"""Claude / Codex CLI 호출 공통 유틸리티."""
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from utils.json_utils import parse_json

_RETRY_DELAYS = (30, 60, 120)


def _resolve_exe(name: str) -> str:
    """Windows에서 npm 이 설치하는 CLI(codex 등)는 `<name>.cmd` 배치 파일이라, shell=False
    subprocess.run(["codex", ...]) 는 CreateProcess 가 PATHEXT 를 확장하지 않아 그냥 "codex"
    로는 FileNotFoundError(WinError 2) 가 난다 — shutil.which 로 PATHEXT 를 반영해 실제
    실행 파일 경로를 미리 찾아 넘긴다(못 찾으면 원래 이름 그대로 반환해 에러가 자연히 드러나게 둔다)."""
    return shutil.which(name) or name


def call_claude(prompt: str, timeout: int = 300, allowed_tools: list[str] | None = None,
                mcp_config: str | None = None) -> dict:
    """Claude CLI로 프롬프트를 실행하고 JSON 결과를 반환한다.

    --output-format json 의 envelope(subtype)으로 과부하·중단을 판별해 자동 재시도한다.
    텍스트에 "529"/"Overloaded" 가 있는지만 보는 방식은 모델이 도중에 끊겨도
    감지하지 못해 잘린 JSON이 그대로 parse_failed 로 빠지는 문제가 있었다.

    allowed_tools: 예) ["WebSearch"] — 헤드리스 -p 모드는 기본적으로 WebSearch 등
    권한이 필요한 툴을 자동 거부(permission_denials)한다. 실제 웹 검색이 필요하면 지정한다.
    mcp_config: MCP 서버 설정 파일 경로(예: 프로젝트 루트의 `.mcp.json`). 헤드리스 -p 모드는
    프로젝트 `.mcp.json` 을 암묵적으로 신뢰하지 않을 수 있어, MCP 도구를 쓰려면 이 인자로
    명시적으로 지정해야 한다. allowed_tools 에 그 서버의 도구명(`mcp__<server>__<tool>`)도
    함께 넣어야 실제로 호출을 허용한다.
    """
    cmd = ["claude", "-p", prompt, "--output-format", "json"]
    if mcp_config:
        cmd += ["--mcp-config", mcp_config]
    if allowed_tools:
        cmd += ["--allowedTools", *allowed_tools]
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as f:
        out_path = Path(f.name)
    result_text = ""
    for attempt, delay in enumerate((*_RETRY_DELAYS, None), start=1):
        try:
            with open(out_path, "w", encoding="utf-8") as out_f:
                subprocess.run(cmd, stdout=out_f, stderr=subprocess.DEVNULL, timeout=timeout)
            raw = out_path.read_text(encoding="utf-8")
            result_text, retry_needed = _unwrap_envelope(raw)
        except subprocess.TimeoutExpired:
            result_text, retry_needed = f'{{"error": "timeout after {timeout}s"}}', True
        if not retry_needed:
            return parse_json(result_text)
        if delay is None:
            break
        print(f"      Claude 응답 비정상 종료(또는 타임아웃), {delay}초 후 재시도 ({attempt}/{len(_RETRY_DELAYS)})...")
        time.sleep(delay)
    return parse_json(result_text)


def _unwrap_envelope(raw: str) -> tuple[str, bool]:
    """--output-format json envelope에서 모델 응답 텍스트와 재시도 필요 여부를 꺼낸다."""
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError:
        return raw, "529" in raw or "Overloaded" in raw
    result_text = envelope.get("result", "")
    retry_needed = envelope.get("subtype") != "success"
    return result_text, retry_needed


def call_codex(prompt: str, model: str | None = None, timeout: int = 300) -> dict:
    """Codex CLI로 프롬프트를 실행하고 JSON 결과를 반환한다.

    prompt는 CLI 인자가 아니라 stdin(`-`)으로 넘긴다 — Windows에서 codex(.cmd 배치 파일, npm
    설치)는 cmd.exe를 거쳐 실행되는데, cmd.exe의 명령줄 길이 제한(8191자)을 넘는 프롬프트를
    인자로 주면 "The command line is too long." 로 조용히 실패해(returncode=1, out_file 빈 채로
    남음) parse_failed 로만 보인다. codex exec는 PROMPT 인자가 없거나 `-`면 stdin에서 읽는다.
    """
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        out_file = Path(f.name)
    cmd = [_resolve_exe("codex"), "exec", "--dangerously-bypass-approvals-and-sandbox", "-o", str(out_file)]
    if model:
        cmd += ["-m", model]
    cmd.append("-")
    subprocess.run(cmd, input=prompt, text=True, encoding="utf-8",
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout)
    return parse_json(out_file.read_text(encoding="utf-8"))
