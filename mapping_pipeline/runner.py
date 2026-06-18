"""mapping_pipeline 공통 실행 로직 — CLI·GUI·API에서 재사용한다."""
import dataclasses
import json
import time
from collections.abc import Callable
from pathlib import Path

from pipeline.cuts import Cut, detect_cuts, merge_to_max_cuts
from pipeline.frames import extract_frames_at_fps
from pipeline.keyframe import extract_keyframes

_OUTPUT_ROOT = Path("output")
_MAX_THRESHOLD_ITER = 10

BACKEND_TRANSNETV2 = "transnetv2"
BACKEND_SCENEDETECT = "scenedetect"
DEFAULT_BACKEND = BACKEND_TRANSNETV2

LLM_GEMINI = "gemini"
LLM_OPENAI = "openai"
DEFAULT_LLM_BACKEND = LLM_OPENAI

_DEFAULT_LLM_MODEL: dict[str, str] = {
    LLM_GEMINI: "models/gemini-2.5-flash-lite",
    LLM_OPENAI: "gpt-4o-mini",
}

_THRESHOLD_RANGE: dict[str, tuple[float, float]] = {
    BACKEND_TRANSNETV2: (0.05, 0.95),
    BACKEND_SCENEDETECT: (1.0, 100.0),
}
_DEFAULT_THRESHOLD: dict[str, float] = {
    BACKEND_TRANSNETV2: 0.3,
    BACKEND_SCENEDETECT: 27.0,
}


def default_llm_model(llm_backend: str) -> str:
    """LLM 백엔드별 기본 모델명을 반환한다."""
    return _DEFAULT_LLM_MODEL.get(llm_backend, _DEFAULT_LLM_MODEL[DEFAULT_LLM_BACKEND])


def _call_detect(video_path: Path, threshold: float, backend: str) -> list[Cut]:
    if backend == BACKEND_TRANSNETV2:
        from pipeline.transnetv2_cuts import detect_cuts_transnetv2
        return detect_cuts_transnetv2(video_path, threshold=threshold)
    return detect_cuts(video_path, threshold=threshold)


def _detect_cuts_in_range(
    video_path: Path,
    min_cuts: int,
    max_cuts: int,
    initial_threshold: float,
    backend: str,
    log: Callable[[str], None],
) -> tuple[list[Cut], float]:
    """threshold를 이진 탐색으로 조정해 컷 수를 [min_cuts, max_cuts]로 맞춘다."""
    lo, hi = _THRESHOLD_RANGE[backend]
    threshold = initial_threshold
    cuts = _call_detect(video_path, threshold, backend)
    log(f"    threshold={threshold:.3f} -> {len(cuts)} cuts")

    for i in range(1, _MAX_THRESHOLD_ITER):
        n = len(cuts)
        if min_cuts <= n <= max_cuts:
            break
        lo, hi = (threshold, hi) if n > max_cuts else (lo, threshold)
        threshold = (lo + hi) / 2
        cuts = _call_detect(video_path, threshold, backend)
        log(f"    [iter {i}] threshold={threshold:.3f} -> {len(cuts)} cuts")

    return cuts, threshold


def _step_detect_cuts(
    video_path: Path,
    min_cuts: int | None,
    max_cuts: int,
    threshold: float,
    backend: str,
    log: Callable[[str], None],
) -> list[Cut]:
    if min_cuts is not None:
        log(f"[1] Detecting cuts... ({backend}, auto threshold, min={min_cuts}, max={max_cuts})")
        cuts, _ = _detect_cuts_in_range(video_path, min_cuts, max_cuts, threshold, backend, log)
        if len(cuts) > max_cuts:
            log(f"    Search ended with {len(cuts)} cuts; applying merge_to_max_cuts({max_cuts})")
            return merge_to_max_cuts(cuts, max_cuts)
        return cuts
    log(f"[1] Detecting cuts... ({backend}, threshold={threshold:.3f}, max_cuts={max_cuts})")
    return merge_to_max_cuts(_call_detect(video_path, threshold, backend), max_cuts)


def _analyze_cuts(cuts: list[Cut], frames_dir: Path, llm_backend: str, llm_model: str) -> list[dict]:
    if llm_backend == LLM_OPENAI:
        from pipeline.cut_analysis_openai import analyze_cuts_openai
        return analyze_cuts_openai(cuts, frames_dir, {}, model=llm_model)
    from pipeline.cut_analysis_gemini import analyze_cuts_gemini
    return analyze_cuts_gemini(cuts, frames_dir, {}, model=llm_model)


def _map_cuts_to_scenes(cut_analysis: list[dict], scenario_txt: str, llm_backend: str, llm_model: str) -> list[dict]:
    if llm_backend == LLM_OPENAI:
        from mapping_pipeline.cut_mapper_openai import map_cuts_to_scenes_openai
        return map_cuts_to_scenes_openai(cut_analysis, scenario_txt, model=llm_model)
    from mapping_pipeline.cut_mapper import map_cuts_to_scenes
    return map_cuts_to_scenes(cut_analysis, scenario_txt, model=llm_model)


def _reset_tokens(llm_backend: str) -> None:
    if llm_backend == LLM_OPENAI:
        from utils.openai_caller import reset_token_usage
    else:
        from utils.gemini_caller import reset_token_usage
    reset_token_usage()


def _read_tokens(llm_backend: str) -> dict[str, int]:
    if llm_backend == LLM_OPENAI:
        from utils.openai_caller import get_token_usage
    else:
        from utils.gemini_caller import get_token_usage
    return get_token_usage()


def run_mapping_pipeline(
    video_path: Path,
    scenario_txt: str,
    out_dir: Path | None = None,
    min_cuts: int | None = None,
    max_cuts: int = 10,
    threshold: float | None = None,
    backend: str = DEFAULT_BACKEND,
    llm_backend: str = DEFAULT_LLM_BACKEND,
    llm_model: str | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> dict:
    """영상 + 시나리오 텍스트 → cut_analysis·cut_scene_mapping·tokens 딕셔너리를 반환한다.

    backend     — 컷 감지 백엔드 (transnetv2 / scenedetect)
    llm_backend — cut_analysis · cut_mapper에 사용할 LLM 백엔드 (gemini / openai)
    llm_model   — LLM 모델명. 미지정 시 백엔드별 기본값.
    """
    if out_dir is None:
        out_dir = _OUTPUT_ROOT / video_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    resolved_threshold = threshold if threshold is not None else _DEFAULT_THRESHOLD.get(backend, 0.3)
    resolved_model = llm_model or default_llm_model(llm_backend)

    _reset_tokens(llm_backend)
    pipeline_start = time.time()

    def log(msg: str) -> None:
        print(msg)
        if on_progress:
            on_progress(msg)

    cuts = _step_detect_cuts(video_path, min_cuts, max_cuts, resolved_threshold, backend, log)
    _save_json(out_dir / "cuts.json", [dataclasses.asdict(c) for c in cuts])
    log(f"    Cut count: {len(cuts)} -> cuts.json")

    log("[2] Extracting keyframes...")
    keyframes = extract_keyframes(video_path, cuts, out_dir / "keyframes")
    log(f"    {len(keyframes)} images -> keyframes/")

    log("[3] Extracting frames... (fps=2)")
    frames = extract_frames_at_fps(video_path, out_dir / "frames", fps=2.0)
    log(f"    {len(frames)} images -> frames/")

    log(f"[4] Analyzing cuts... ({llm_backend}:{resolved_model}, cuts={len(cuts)})")
    cut_analysis = _analyze_cuts(cuts, out_dir / "frames", llm_backend, resolved_model)
    _save_json(out_dir / "cut_analysis.json", cut_analysis)
    log(f"    Done - {len(cut_analysis)} cuts -> cut_analysis.json")

    log(f"[5] Mapping cuts to scenes... ({llm_backend}:{resolved_model})")
    cut_scene_mapping = _map_cuts_to_scenes(cut_analysis, scenario_txt, llm_backend, resolved_model)
    tokens = _read_tokens(llm_backend)
    pipeline_time = round(time.time() - pipeline_start, 2)

    mapping_output = {
        "scenes": cut_scene_mapping,
        "tokens": tokens,
        "pipeline_time_s": pipeline_time,
        "llm_backend": llm_backend,
        "llm_model": resolved_model,
    }
    _save_json(out_dir / "cut_scene_mapping.json", mapping_output)
    log(f"    Done - {len(cut_scene_mapping)} scenes -> cut_scene_mapping.json")
    log(f"    Tokens ({llm_backend}): input={tokens['input']}, output={tokens['output']}, thinking={tokens['thinking']}")
    log(f"    Pipeline total time: {pipeline_time}s")

    return {
        "cut_analysis": cut_analysis,
        "cut_scene_mapping": cut_scene_mapping,
        "tokens": tokens,
        "pipeline_time_s": pipeline_time,
        "llm_backend": llm_backend,
        "llm_model": resolved_model,
        "out_dir": str(out_dir),
    }


def _save_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
