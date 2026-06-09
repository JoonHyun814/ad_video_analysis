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


def run_mapping_pipeline(
    video_path: Path,
    scenario_txt: str,
    out_dir: Path | None = None,
    max_cuts: int = 10,
    threshold: float = 27.0,
    gemini_model: str = DEFAULT_MODEL,
    on_progress: Callable[[str], None] | None = None,
) -> dict:
    """영상 + 시나리오 텍스트 → cut_analysis·cut_scene_mapping·tokens 딕셔너리를 반환한다."""
    if out_dir is None:
        out_dir = _OUTPUT_ROOT / video_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    reset_token_usage()
    pipeline_start = time.time()

    def log(msg: str) -> None:
        print(msg)
        if on_progress:
            on_progress(msg)

    log(f"[1] 컷 감지 중... (threshold={threshold}, max_cuts={max_cuts})")
    cuts = merge_to_max_cuts(detect_cuts(video_path, threshold=threshold), max_cuts)
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
