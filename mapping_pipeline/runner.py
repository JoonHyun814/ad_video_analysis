"""mapping_pipeline 공통 실행 로직 — CLI·GUI·API에서 재사용한다."""
import dataclasses
import json
import time
from collections.abc import Callable
from pathlib import Path

from mapping_pipeline.cut_mapper import map_cuts_to_scenes
from pipeline.cut_analysis_gemini import analyze_cuts_gemini
from pipeline.cuts import Cut, detect_cuts, merge_to_max_cuts
from pipeline.frames import extract_frames_at_fps
from pipeline.keyframe import extract_keyframes
from utils.gemini_caller import DEFAULT_MODEL, get_token_usage, reset_token_usage

_OUTPUT_ROOT = Path("output")
_MAX_THRESHOLD_ITER = 10

BACKEND_TRANSNETV2 = "transnetv2"
BACKEND_SCENEDETECT = "scenedetect"
DEFAULT_BACKEND = BACKEND_TRANSNETV2

_THRESHOLD_RANGE: dict[str, tuple[float, float]] = {
    BACKEND_TRANSNETV2: (0.05, 0.95),
    BACKEND_SCENEDETECT: (1.0, 100.0),
}
_DEFAULT_THRESHOLD: dict[str, float] = {
    BACKEND_TRANSNETV2: 0.3,
    BACKEND_SCENEDETECT: 27.0,
}


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
    log(f"    threshold={threshold:.3f} → {len(cuts)}컷")

    for i in range(1, _MAX_THRESHOLD_ITER):
        n = len(cuts)
        if min_cuts <= n <= max_cuts:
            break
        lo, hi = (threshold, hi) if n > max_cuts else (lo, threshold)
        threshold = (lo + hi) / 2
        cuts = _call_detect(video_path, threshold, backend)
        log(f"    [iter {i}] threshold={threshold:.3f} → {len(cuts)}컷")

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
        log(f"[1] 컷 감지 중... ({backend}, threshold 자동 조정, min={min_cuts}, max={max_cuts})")
        cuts, _ = _detect_cuts_in_range(video_path, min_cuts, max_cuts, threshold, backend, log)
        if len(cuts) > max_cuts:
            log(f"    루프 종료 후 {len(cuts)}컷 초과 → merge_to_max_cuts({max_cuts}) 적용")
            return merge_to_max_cuts(cuts, max_cuts)
        return cuts
    log(f"[1] 컷 감지 중... ({backend}, threshold={threshold:.3f}, max_cuts={max_cuts})")
    return merge_to_max_cuts(_call_detect(video_path, threshold, backend), max_cuts)


def run_mapping_pipeline(
    video_path: Path,
    scenario_txt: str,
    out_dir: Path | None = None,
    min_cuts: int | None = None,
    max_cuts: int = 10,
    threshold: float | None = None,
    backend: str = DEFAULT_BACKEND,
    gemini_model: str = DEFAULT_MODEL,
    on_progress: Callable[[str], None] | None = None,
) -> dict:
    """영상 + 시나리오 텍스트 → cut_analysis·cut_scene_mapping·tokens 딕셔너리를 반환한다."""
    if out_dir is None:
        out_dir = _OUTPUT_ROOT / video_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    resolved_threshold = threshold if threshold is not None else _DEFAULT_THRESHOLD.get(backend, 0.3)

    reset_token_usage()
    pipeline_start = time.time()

    def log(msg: str) -> None:
        print(msg)
        if on_progress:
            on_progress(msg)

    cuts = _step_detect_cuts(video_path, min_cuts, max_cuts, resolved_threshold, backend, log)
    _save_json(out_dir / "cuts.json", [dataclasses.asdict(c) for c in cuts])
    log(f"    컷 수: {len(cuts)} → cuts.json")

    log("[2] Keyframe 추출 중...")
    keyframes = extract_keyframes(video_path, cuts, out_dir / "keyframes")
    log(f"    {len(keyframes)}장 → keyframes/")

    log("[3] Frames 추출 중... (fps=2)")
    frames = extract_frames_at_fps(video_path, out_dir / "frames", fps=2.0)
    log(f"    {len(frames)}장 → frames/")

    log(f"[4] Cut 분석 중... ({gemini_model}, 컷 수={len(cuts)})")
    cut_analysis = analyze_cuts_gemini(cuts, out_dir / "frames", {}, model=gemini_model)
    _save_json(out_dir / "cut_analysis.json", cut_analysis)
    log(f"    완료 — {len(cut_analysis)}컷 → cut_analysis.json")

    log("[5] Cut-Scene 매핑 중... (gemini)")
    cut_scene_mapping = map_cuts_to_scenes(cut_analysis, scenario_txt, model=gemini_model)
    tokens = get_token_usage()
    pipeline_time = round(time.time() - pipeline_start, 2)

    mapping_output = {
        "scenes": cut_scene_mapping,
        "tokens": tokens,
        "pipeline_time_s": pipeline_time,
    }
    _save_json(out_dir / "cut_scene_mapping.json", mapping_output)
    log(f"    완료 — {len(cut_scene_mapping)}scene → cut_scene_mapping.json")
    log(f"    토큰: input={tokens['input']}, output={tokens['output']}, thinking={tokens['thinking']}")
    log(f"    파이프라인 총 시간: {pipeline_time}s")

    return {
        "cut_analysis": cut_analysis,
        "cut_scene_mapping": cut_scene_mapping,
        "tokens": tokens,
        "pipeline_time_s": pipeline_time,
        "out_dir": str(out_dir),
    }


def _save_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
