"""논문 3.3 Vision Design Methodology Extractor — 제로샷 프롬프트로 훅의 주요 참여 기법을 추출한다.

논문은 Llama MLLM 을 썼고, 여기서는 기존 프로젝트와 같은 방식으로 claude -p / codex exec 를 호출한다.
"""
import shutil
import subprocess
import tempfile
from pathlib import Path

from hook_pipeline.config import ensure_legacy_on_path

LLM_BACKENDS = ("claude", "codex")
_TIMEOUT = 300
_MAX_ATTEMPTS = 2

# 논문 원문 프롬프트 (변경 없음)
PAPER_PROMPT = """After examining the video and text advertisement titled "{title}" with the body texts "{body}", determine the primary method used by the advertiser to engage the audience. Base your selection on the actual content of the advertisement without making assumptions or interpretations.

Respond using the JSON format.
**JSON Response Format:**
{{
"methodology": "Methodology chosen by the advertiser",
"rationale": "Provide a concise explanation based on specific elements observed in the advertisement that supports why this option best represents the primary engagement strategy used."
}}"""

# CLI 에 프레임을 넘기기 위한 안내문 (논문 프롬프트 앞뒤에만 덧붙인다)
_CLAUDE_PREFIX = """The following image files are frames sampled, in temporal order, from the first {hook_sec:g} seconds (the hooking period) of a video advertisement. Read every file before answering.
{frame_list}

"""
_CODEX_PREFIX = """The attached images are frames sampled, in temporal order, from the first {hook_sec:g} seconds (the hooking period) of a video advertisement. Frame timestamps: {times}.

"""
_SUFFIX = "\n\nOutput only the JSON object, without markdown code fences."


def extract_methodology(
    frames: list[dict], title: str, body: str, backend: str, hook_sec: float, model: str | None = None,
) -> dict:
    """{"methodology", "rationale"} 를 반환한다. 파싱 실패 시 1회 재시도 후 error 키를 담아 반환한다."""
    ensure_legacy_on_path()
    from utils.json_utils import parse_json

    core = PAPER_PROMPT.format(title=title, body=body or "(none)")
    result: dict = {}
    for _ in range(_MAX_ATTEMPTS):
        raw = _call_claude(frames, core, hook_sec, model) if backend == "claude" else _call_codex(frames, core, hook_sec, model)
        result = parse_json(raw)
        if isinstance(result.get("methodology"), str) and isinstance(result.get("rationale"), str):
            return {"methodology": result["methodology"].strip(), "rationale": result["rationale"].strip()}
    return {"error": "invalid_response", "raw": result}


def build_prompt(frames: list[dict], core: str, hook_sec: float, backend: str) -> str:
    """백엔드별 최종 프롬프트 문자열 (디버깅·기록용으로도 사용)."""
    if backend == "claude":
        listing = "\n".join(f"- {f['path']} (t={f['time_sec']:.2f}s)" for f in frames)
        return _CLAUDE_PREFIX.format(hook_sec=hook_sec, frame_list=listing) + core + _SUFFIX
    times = ", ".join(f"{f['time_sec']:.2f}s" for f in frames)
    return _CODEX_PREFIX.format(hook_sec=hook_sec, times=times) + core + _SUFFIX


def _call_claude(frames: list[dict], core: str, hook_sec: float, model: str | None) -> str:
    prompt = build_prompt(frames, core, hook_sec, "claude")
    frames_dir = str(Path(frames[0]["path"]).parent)
    cmd = [_resolve_exe("claude"), "-p", "--add-dir", frames_dir, "--allowedTools", "Read"]
    if model:
        cmd += ["--model", model]
    result = subprocess.run(
        cmd, input=prompt, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=_TIMEOUT,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude -p 실패: {_tail(result.stderr or result.stdout)}")
    return result.stdout


def _call_codex(frames: list[dict], core: str, hook_sec: float, model: str | None) -> str:
    prompt = build_prompt(frames, core, hook_sec, "codex")
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        out_file = Path(f.name)
    cmd = [_resolve_exe("codex"), "exec"]
    for fr in frames:
        cmd += ["-i", fr["path"]]
    cmd += ["--sandbox", "read-only", "--skip-git-repo-check", "-o", str(out_file)]
    if model:
        cmd += ["-m", model]
    cmd.append("-")  # 프롬프트는 stdin 으로 전달 (Windows .cmd 래퍼의 인자 깨짐 방지)
    try:
        result = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=_TIMEOUT,
        )
        text = out_file.read_text(encoding="utf-8") if out_file.exists() else ""
        if result.returncode != 0 or not text.strip():
            raise RuntimeError(f"codex exec 실패: {_tail(result.stderr or result.stdout)}")
        return text
    finally:
        out_file.unlink(missing_ok=True)


def _tail(text: str, lines: int = 3) -> str:
    """CLI 오류 메시지의 마지막 몇 줄 (사용량 한도·인증 오류 등을 그대로 보여주기 위함)."""
    return " | ".join(line.strip() for line in text.strip().splitlines()[-lines:]) or "(출력 없음)"


def _resolve_exe(name: str) -> str:
    exe = shutil.which(name)
    if exe is None:
        raise FileNotFoundError(f"'{name}' CLI 를 PATH 에서 찾을 수 없습니다.")
    return exe
