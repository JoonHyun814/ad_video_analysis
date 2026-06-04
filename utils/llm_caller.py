"""Claude / Codex CLI 호출 공통 유틸리티."""
import subprocess
import tempfile
import time
from pathlib import Path

from utils.json_utils import parse_json

_RETRY_DELAYS = (30, 60, 120)


def call_claude(prompt: str, timeout: int = 300) -> dict:
    """Claude CLI로 프롬프트를 실행하고 JSON 결과를 반환한다.

    stdout을 파일로 받아 PIPE 버퍼 문제를 방지하고, 529 과부하 시 자동 재시도한다.
    """
    cmd = ["claude", "-p", prompt]
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as f:
        out_path = Path(f.name)
    text = ""
    for attempt, delay in enumerate((*_RETRY_DELAYS, None), start=1):
        with open(out_path, "w", encoding="utf-8") as out_f:
            subprocess.run(cmd, stdout=out_f, stderr=subprocess.DEVNULL, timeout=timeout)
        text = out_path.read_text(encoding="utf-8")
        if "529" not in text and "Overloaded" not in text:
            return parse_json(text)
        if delay is None:
            break
        print(f"      API 과부하(529), {delay}초 후 재시도 ({attempt}/{len(_RETRY_DELAYS)})...")
        time.sleep(delay)
    return parse_json(text)


def call_codex(prompt: str, model: str | None = None, timeout: int = 300) -> dict:
    """Codex CLI로 프롬프트를 실행하고 JSON 결과를 반환한다."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        out_file = Path(f.name)
    cmd = ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", "-o", str(out_file)]
    if model:
        cmd += ["-m", model]
    cmd.append(prompt)
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout)
    return parse_json(out_file.read_text(encoding="utf-8"))
