"""논문 3.3 Vision Design Methodology Extractor — 제로샷 프롬프트로 훅의 주요 참여 기법을 추출한다.

논문은 Llama MLLM 을 썼고, 여기서는 claude -p / codex exec / Qwen2.5-VL 로컬 모델을 지원한다.
"""
import gc
import shutil
import subprocess
import tempfile
from pathlib import Path

from hook_pipeline.config import ensure_legacy_on_path

LLM_BACKENDS = ("claude", "codex", "qwen_vl")
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
_QWEN_PREFIX = """The following images are frames sampled, in temporal order, from the first {hook_sec:g} seconds (the hooking period) of a video advertisement. Frame timestamps: {times}.
Analyze all provided frames before answering.

"""
_SUFFIX = "\n\nOutput only the JSON object, without markdown code fences."

# 로컬 Qwen 모델 싱글턴 (배치 처리 중 재로딩 방지)
_qwen_model = None


def extract_methodology(
    frames: list[dict],
    title: str,
    body: str,
    backend: str,
    hook_sec: float,
    model: str | None = None,
    qwen_model_path: str | Path | None = None,
    camera_motion: dict | None = None,
    visual_features: dict | None = None,
) -> dict:
    """{"methodology", "rationale"} 를 반환한다. 파싱 실패 시 1회 재시도 후 error 키를 담아 반환한다."""
    ensure_legacy_on_path()
    from utils.json_utils import parse_json

    core = PAPER_PROMPT.format(title=title, body=body or "(none)")
    result: dict = {}
    for _ in range(_MAX_ATTEMPTS):
        if backend == "claude":
            raw = _call_claude(frames, core, hook_sec, model, camera_motion, visual_features)
        elif backend == "codex":
            raw = _call_codex(frames, core, hook_sec, model, camera_motion, visual_features)
        else:
            raw = _call_qwen_vl(frames, core, hook_sec, qwen_model_path, camera_motion, visual_features)
        result = parse_json(raw)
        if isinstance(result.get("methodology"), str) and isinstance(result.get("rationale"), str):
            return {"methodology": result["methodology"].strip(), "rationale": result["rationale"].strip()}
    return {"error": "invalid_response", "raw": result}


def build_prompt(
    frames: list[dict],
    core: str,
    hook_sec: float,
    backend: str,
    camera_motion: dict | None = None,
    visual_features: dict | None = None,
) -> str:
    """백엔드별 최종 프롬프트 문자열 (디버깅·기록용으로도 사용)."""
    cm_text = _format_camera_motion(camera_motion)
    vf_text = _format_visual_features(visual_features)
    context = cm_text + vf_text
    if backend == "claude":
        listing = "\n".join(f"- {f['path']} (t={f['time_sec']:.2f}s)" for f in frames)
        return _CLAUDE_PREFIX.format(hook_sec=hook_sec, frame_list=listing) + context + core + _SUFFIX
    if backend == "qwen_vl":
        times = ", ".join(f"{f['time_sec']:.2f}s" for f in frames)
        return _QWEN_PREFIX.format(hook_sec=hook_sec, times=times) + context + core + _SUFFIX
    times = ", ".join(f"{f['time_sec']:.2f}s" for f in frames)
    return _CODEX_PREFIX.format(hook_sec=hook_sec, times=times) + context + core + _SUFFIX


def _format_camera_motion(cm: dict | None) -> str:
    """camera_motion dict → 프롬프트 중간 삽입 텍스트. 데이터 없으면 빈 문자열."""
    from hook_pipeline.camera_motion import format_for_prompt
    return format_for_prompt(cm) + "\n" if cm and cm.get("n_pairs", 0) > 0 else ""


def _format_visual_features(vf: dict | None) -> str:
    """visual_features dict → 프롬프트 중간 삽입 텍스트. 데이터 없으면 빈 문자열."""
    from hook_pipeline.visual_features import format_for_prompt
    text = format_for_prompt(vf)
    return text + "\n" if text else ""


def release_qwen() -> None:
    """배치 종료 시 Qwen 모델을 내려 GPU 메모리를 비운다."""
    global _qwen_model
    _qwen_model = None
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def _call_qwen_vl(
    frames: list[dict],
    core: str,
    hook_sec: float,
    model_path: str | Path | None,
    camera_motion: dict | None = None,
    visual_features: dict | None = None,
) -> str:
    global _qwen_model
    from PIL import Image
    from utils.qwen_vl_caller import QwenVLModel

    if _qwen_model is None:
        if model_path is None:
            from utils.env_loader import get_model_root
            from utils.qwen_vl_caller import DEFAULT_MODEL_NAME
            model_path = get_model_root() / DEFAULT_MODEL_NAME
        _qwen_model = QwenVLModel(model_path)

    images = [Image.open(f["path"]).convert("RGB") for f in frames]
    prompt = build_prompt(frames, core, hook_sec, "qwen_vl", camera_motion, visual_features)
    result = _qwen_model.infer_multi(images, prompt, max_new_tokens=512)
    return result.text


def _call_claude(
    frames: list[dict], core: str, hook_sec: float, model: str | None,
    camera_motion: dict | None = None,
    visual_features: dict | None = None,
) -> str:
    prompt = build_prompt(frames, core, hook_sec, "claude", camera_motion, visual_features)
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


def _call_codex(
    frames: list[dict], core: str, hook_sec: float, model: str | None,
    camera_motion: dict | None = None,
    visual_features: dict | None = None,
) -> str:
    prompt = build_prompt(frames, core, hook_sec, "codex", camera_motion, visual_features)
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        out_file = Path(f.name)
    cmd = [_resolve_exe("codex"), "exec"]
    for fr in frames:
        cmd += ["-i", fr["path"]]
    cmd += ["--sandbox", "read-only", "--skip-git-repo-check", "-o", str(out_file)]
    if model:
        cmd += ["-m", model]
    cmd.append("-")
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
