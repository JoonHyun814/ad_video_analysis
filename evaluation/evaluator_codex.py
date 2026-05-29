"""codex 백엔드 시나리오 평가."""
import subprocess
import tempfile
from pathlib import Path

from evaluation.evaluator import _compute_scores, _parse_json, build_eval_prompt


def evaluate_scenario_codex(brief: dict, scenario: dict, model: str | None = None) -> dict:
    """codex exec 로 시나리오를 평가한다."""
    prompt = build_eval_prompt(brief, scenario)
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        out_file = Path(f.name)

    cmd = ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", "-o", str(out_file)]
    if model:
        cmd += ["-m", model]
    cmd.append(prompt)

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600)
    raw = _parse_json(out_file.read_text(encoding="utf-8"))
    return _compute_scores(raw)
