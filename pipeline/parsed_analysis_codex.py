"""scenario_analysis 결과를 DB 저장용 parsed 구조로 정제한다 (codex 백엔드)."""
import subprocess
import tempfile
from pathlib import Path

from pipeline.cuts import Cut
from pipeline.parsed_analysis import _inject_meta, _parse_json, build_prompt


def analyze_parsed_codex(
    scenario: dict,
    cuts: list[Cut],
    cut_analysis: list[dict],
    scene_analysis: list[dict],
    stt_segments: list[dict],
    audio_data: dict | None,
    model: str | None = None,
) -> dict:
    """codex exec 로 parsed 구조를 생성한다."""
    prompt = build_prompt(scenario, cuts, cut_analysis, scene_analysis, stt_segments, audio_data)

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        out_file = Path(f.name)

    cmd = ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", "-o", str(out_file)]
    if model:
        cmd += ["-m", model]
    cmd.append(prompt)

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600)
    result = _parse_json(out_file.read_text(encoding="utf-8"))
    _inject_meta(result, cuts, model or "codex")
    return result
