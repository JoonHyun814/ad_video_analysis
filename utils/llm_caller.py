"""Claude / Codex CLI 호출 공통 유틸리티."""
import json
import subprocess
import tempfile
import time
from pathlib import Path

from utils.json_utils import parse_json

_RETRY_DELAYS = (30, 60, 120)


def call_claude(prompt: str, timeout: int = 300) -> dict:
    """Claude CLI로 프롬프트를 실행하고 JSON 결과를 반환한다.

    --output-format json 의 envelope(subtype)으로 과부하·중단을 판별해 자동 재시도한다.
    텍스트에 "529"/"Overloaded" 가 있는지만 보는 방식은 모델이 도중에 끊겨도
    감지하지 못해 잘린 JSON이 그대로 parse_failed 로 빠지는 문제가 있었다.
    """
    cmd = ["claude", "-p", prompt, "--output-format", "json"]
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as f:
        out_path = Path(f.name)
    result_text = ""
    for attempt, delay in enumerate((*_RETRY_DELAYS, None), start=1):
        with open(out_path, "w", encoding="utf-8") as out_f:
            subprocess.run(cmd, stdout=out_f, stderr=subprocess.DEVNULL, timeout=timeout)
        raw = out_path.read_text(encoding="utf-8")
        result_text, retry_needed = _unwrap_envelope(raw)
        if not retry_needed:
            return parse_json(result_text)
        if delay is None:
            break
        print(f"      Claude 응답 비정상 종료, {delay}초 후 재시도 ({attempt}/{len(_RETRY_DELAYS)})...")
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
    """Codex CLI로 프롬프트를 실행하고 JSON 결과를 반환한다."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        out_file = Path(f.name)
    cmd = ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", "-o", str(out_file)]
    if model:
        cmd += ["-m", model]
    cmd.append(prompt)
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout)
    return parse_json(out_file.read_text(encoding="utf-8"))
