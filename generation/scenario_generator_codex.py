"""브리프 기반 광고 시나리오 생성 (codex 백엔드)."""
import subprocess
import tempfile
from pathlib import Path

from generation.scenario_generator import _parse_json, build_scenario_prompt


def generate_scenario_codex(brief: dict, model: str | None = None) -> dict:
    """codex exec 로 시나리오를 생성한다."""
    prompt = build_scenario_prompt(brief)
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        out_file = Path(f.name)

    cmd = ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", "-o", str(out_file)]
    if model:
        cmd += ["-m", model]
    cmd.append(prompt)

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600)
    return _parse_json(out_file.read_text(encoding="utf-8"))
