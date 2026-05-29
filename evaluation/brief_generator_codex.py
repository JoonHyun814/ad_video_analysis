"""codex 백엔드 브리프 추출."""
import subprocess
import tempfile
from pathlib import Path

from evaluation.brief_generator import _parse_json, build_brief_prompt


def generate_brief_codex(scenario: dict, model: str | None = None) -> dict:
    """codex exec 로 브리프를 추출한다."""
    prompt = build_brief_prompt(scenario)
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        out_file = Path(f.name)

    cmd = ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", "-o", str(out_file)]
    if model:
        cmd += ["-m", model]
    cmd.append(prompt)

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    return _parse_json(out_file.read_text(encoding="utf-8"))
