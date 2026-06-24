"""영상 mp4 + 시나리오 txt → cut-scene 매핑 파이프라인."""
import argparse
import dataclasses
import json
import time
from pathlib import Path

from pipeline.cuts import Cut, merge_to_max_cuts
from pipeline.frames import extract_frames_at_fps
from pipeline.keyframe import extract_keyframes
from mapping_pipeline.runner import (
    BACKEND_TRANSNETV2,
    BACKEND_SCENEDETECT,
    DEFAULT_BACKEND,
    DEFAULT_LLM_BACKEND,
    LLM_GEMINI,
    LLM_OPENAI,
    _DEFAULT_THRESHOLD,
    _call_detect,
    _analyze_cuts,
    _map_cuts_to_scenes,
    _reset_tokens,
    _read_tokens,
    default_llm_model,
)
from utils.gemini_caller import DEFAULT_MODEL, get_token_usage, reset_token_usage
from utils.io_checks import require_exists, require_valid_json

_OUTPUT_ROOT = Path("output")
_CUT_BACKENDS = (BACKEND_TRANSNETV2, BACKEND_SCENEDETECT)
_LLM_BACKENDS = (LLM_GEMINI, LLM_OPENAI)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="영상 mp4 + 시나리오 txt → cut-scene 매핑")
    p.add_argument("--video_path", type=Path, required=True, help="분석할 영상 파일 경로")
    p.add_argument("--scenario_path", type=Path, required=True,
                   help="시나리오 파일 경로 (.txt 또는 .json)")
    p.add_argument("--out_dir", type=Path, default=None,
                   help=f"결과 저장 루트 디렉토리 (기본: {_OUTPUT_ROOT}/<video_stem>)")
    p.add_argument("--backend", choices=_CUT_BACKENDS, default=DEFAULT_BACKEND,
                   help=f"컷 감지 백엔드 (기본: {DEFAULT_BACKEND})")
    p.add_argument("--llm_backend", choices=_LLM_BACKENDS, default=DEFAULT_LLM_BACKEND,
                   help=f"cut_analysis · cut_mapper에 사용할 LLM 백엔드 (기본: {DEFAULT_LLM_BACKEND})")
    p.add_argument("--llm_model", type=str, default=None,
                   help=f"LLM 모델명. 미지정 시 백엔드별 기본값 "
                        f"(gemini={default_llm_model(LLM_GEMINI)}, openai={default_llm_model(LLM_OPENAI)})")
    p.add_argument("--max_cuts", type=int, default=10, help="최대 컷 수 (기본: 10)")
    p.add_argument("--threshold", type=float, default=None,
                   help="컷 감지 민감도 (기본: transnetv2=0.3 / scenedetect=27.0)")
    p.add_argument("--skip_preprocess", action="store_true",
                   help="전처리(컷 감지·프레임) 건너뜀. out_dir의 기존 파일 재사용")
    p.add_argument("--skip_cut_analysis", action="store_true",
                   help="cut_analysis 건너뜀. 기존 cut_analysis.json 재사용")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    require_exists(args.video_path, "video_path")
    require_exists(args.scenario_path, "scenario_path")

    out = args.out_dir if args.out_dir else _OUTPUT_ROOT / args.video_path.stem
    out.mkdir(parents=True, exist_ok=True)

    llm_backend = args.llm_backend
    llm_model = args.llm_model.strip() if args.llm_model else default_llm_model(llm_backend)
    threshold = args.threshold if args.threshold is not None else _DEFAULT_THRESHOLD[args.backend]

    _reset_tokens(llm_backend)
    pipeline_start = time.time()

    if args.skip_preprocess:
        print("[1-3] Skipping preprocessing - reusing existing files")
        cuts = _load_preprocess_cache(out)
    else:
        cuts = _run_preprocess(args, out, threshold)

    if args.skip_cut_analysis:
        print("[4] Skipping cut analysis - reusing existing cut_analysis.json")
        cut_results = require_valid_json(out / "cut_analysis.json", "cut_analysis")
    else:
        print(f"[4] Analyzing cuts... ({llm_backend}:{llm_model}, cuts={len(cuts)})")
        cut_results = _analyze_cuts(cuts, out / "frames", llm_backend, llm_model)
        _save_json(out / "cut_analysis.json", cut_results)
        print(f"    Done -> {out / 'cut_analysis.json'}")

    print("[5] Reading scenario...")
    scenario_txt = _load_scenario(args.scenario_path)
    print(f"    {len(scenario_txt)} chars")

    print(f"[6] Mapping cuts to scenes... ({llm_backend}:{llm_model})")
    scenes = _map_cuts_to_scenes(cut_results, scenario_txt, llm_backend, llm_model)

    tokens = _read_tokens(llm_backend)
    pipeline_time = round(time.time() - pipeline_start, 2)
    output = {
        "scenes": scenes,
        "tokens": tokens,
        "pipeline_time_s": pipeline_time,
        "llm_backend": llm_backend,
        "llm_model": llm_model,
    }
    _save_json(out / "cut_scene_mapping.json", output)
    print(f"    Done -> {out / 'cut_scene_mapping.json'}")
    print(f"    llm={llm_backend}:{llm_model}")
    print(f"    Tokens: input={tokens['input']}, output={tokens['output']}, thinking={tokens['thinking']}")
    print(f"    Pipeline total time: {pipeline_time}s")


def _run_preprocess(args: argparse.Namespace, out: Path, threshold: float) -> list[Cut]:
    print(f"[1] Detecting cuts... ({args.backend}, threshold={threshold:.3f}, max_cuts={args.max_cuts})")
    cuts = merge_to_max_cuts(
        _call_detect(args.video_path, threshold, args.backend),
        args.max_cuts,
    )
    _save_json(out / "cuts.json", [dataclasses.asdict(c) for c in cuts])
    print(f"    Cut count: {len(cuts)} -> {out / 'cuts.json'}")

    print("[2] Extracting keyframes...")
    keyframes = extract_keyframes(args.video_path, cuts, out / "keyframes")
    print(f"    {len(keyframes)} images -> {out / 'keyframes'}")

    print("[3] Extracting frames... (fps=2)")
    frames = extract_frames_at_fps(args.video_path, out / "frames", fps=2.0)
    print(f"    {len(frames)} images -> {out / 'frames'}")

    return cuts


def _load_preprocess_cache(out: Path) -> list[Cut]:
    cuts_file = out / "cuts.json"
    if not cuts_file.exists():
        raise FileNotFoundError(f"Cache not found: {cuts_file}. Run preprocessing before using --skip_preprocess.")
    cuts = [Cut(**d) for d in _load_json(cuts_file, [])]
    print(f"    Cut count: {len(cuts)}")
    return cuts


def _load_scenario(path: Path) -> str:
    """시나리오 파일을 읽는다. .json이면 포맷된 JSON 문자열로, 그 외엔 원문 그대로 반환한다."""
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
    return text


def _save_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


if __name__ == "__main__":
    main()
