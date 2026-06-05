"""codex 백엔드 시나리오 평가."""
import subprocess
import tempfile
from pathlib import Path

from evaluation.evaluator import _compute_scores, _parse_json, build_eval_prompt, build_eval_prompt_no_brief


def evaluate_scenario_codex(brief: dict, scenario: dict, model: str | None = None) -> dict:
    """codex exec 로 시나리오를 평가한다."""
    prompt = build_eval_prompt(brief, scenario)
    return _run_codex(prompt, model)


def evaluate_scenario_no_brief_codex(scenario: dict, model: str | None = None) -> dict:
    """브리프 없이 시나리오만으로 평가한다 (codex 백엔드). brief_fidelity 항목 제외."""
    prompt = build_eval_prompt_no_brief(scenario)
    return _run_codex(prompt, model)


def _run_codex(prompt: str, model: str | None) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        out_file = Path(f.name)

    cmd = ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", "-o", str(out_file)]
    if model:
        cmd += ["-m", model]
    cmd.append(prompt)

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600)
    raw = _parse_json(out_file.read_text(encoding="utf-8"))
    return _compute_scores(raw)
