"""영상 mp4 + 시나리오 txt → cut-scene 매핑 파이프라인."""
import argparse
import dataclasses
import json
import time
from pathlib import Path

from pipeline.cut_analysis_gemini import analyze_cuts_gemini
from pipeline.cuts import Cut, detect_cuts, merge_to_max_cuts
from pipeline.frames import extract_frames_at_fps
from pipeline.keyframe import extract_keyframes
from mapping_pipeline.cut_mapper import map_cuts_to_scenes
from utils.gemini_caller import DEFAULT_MODEL, get_token_usage, reset_token_usage

_OUTPUT_ROOT = Path("output")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="영상 mp4 + 시나리오 txt → cut-scene 매핑")
    p.add_argument("--video_path", type=Path, required=True, help="분석할 영상 파일 경로")
    p.add_argument("--scenario_path", type=Path, required=True,
                   help="시나리오 파일 경로 (.txt 또는 .json)")
    p.add_argument("--out_dir", type=Path, default=None,
                   help=f"결과 저장 루트 디렉토리 (기본: {_OUTPUT_ROOT}/<video_stem>)")
    p.add_argument("--max_cuts", type=int, default=10, help="최대 컷 수 (기본: 10)")
    p.add_argument("--threshold", type=float, default=27.0,
                   help="scenedetect 컷 감지 민감도 (기본: 27.0)")
    p.add_argument("--gemini_model", type=str, default=DEFAULT_MODEL,
                   help=f"Gemini 모델명 (기본: {DEFAULT_MODEL})")
    p.add_argument("--skip_preprocess", action="store_true",
                   help="전처리(컷 감지·프레임·OCR) 건너뜀. out_dir의 기존 파일 재사용")
    p.add_argument("--skip_cut_analysis", action="store_true",
                   help="cut_analysis 건너뜀. 기존 cut_analysis.json 재사용")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    out = args.out_dir if args.out_dir else _OUTPUT_ROOT / args.video_path.stem
    out.mkdir(parents=True, exist_ok=True)
    reset_token_usage()
    pipeline_start = time.time()

    if args.skip_preprocess:
        print("[1-3] 전처리 생략 — 기존 파일 재사용")
        cuts = _load_preprocess_cache(out)
    else:
        cuts = _run_preprocess(args, out)

    if args.skip_cut_analysis:
        print("[4] Cut 분석 생략 — 기존 cut_analysis.json 재사용")
        cut_results = _load_json(out / "cut_analysis.json", [])
    else:
        print(f"[4] Cut 분석 중... (gemini, 컷 수={len(cuts)})")
        cut_results = analyze_cuts_gemini(cuts, out / "frames", {}, model=args.gemini_model)
        _save_json(out / "cut_analysis.json", cut_results)
        print(f"    완료 → {out / 'cut_analysis.json'}")

    print("[5] 시나리오 읽는 중...")
    scenario_txt = _load_scenario(args.scenario_path)
    print(f"    {len(scenario_txt)}자")

    print("[6] Cut-Scene 매핑 중... (gemini)")
    scenes = map_cuts_to_scenes(cut_results, scenario_txt, model=args.gemini_model)

    output = {
        "scenes": scenes,
        "tokens": get_token_usage(),
        "pipeline_time_s": round(time.time() - pipeline_start, 2),
    }
    _save_json(out / "cut_scene_mapping.json", output)
    print(f"    완료 → {out / 'cut_scene_mapping.json'}")
    tokens = output["tokens"]
    print(f"    토큰: input={tokens['input']}, output={tokens['output']}, thinking={tokens['thinking']}")
    print(f"    파이프라인 총 시간: {output['pipeline_time_s']}s")


def _run_preprocess(args: argparse.Namespace, out: Path) -> list[Cut]:
    print(f"[1] 컷 감지 중... (scenedetect, threshold={args.threshold}, max_cuts={args.max_cuts})")
    cuts = merge_to_max_cuts(
        detect_cuts(args.video_path, threshold=args.threshold),
        args.max_cuts,
    )
    _save_json(out / "cuts.json", [dataclasses.asdict(c) for c in cuts])
    print(f"    컷 수: {len(cuts)} → {out / 'cuts.json'}")

    print("[2] Keyframe 추출 중...")
    keyframes = extract_keyframes(args.video_path, cuts, out / "keyframes")
    print(f"    {len(keyframes)}장 → {out / 'keyframes'}")

    print("[3] Frames 추출 중... (fps=2)")
    frames = extract_frames_at_fps(args.video_path, out / "frames", fps=2.0)
    print(f"    {len(frames)}장 → {out / 'frames'}")

    return cuts


def _load_preprocess_cache(out: Path) -> list[Cut]:
    cuts_file = out / "cuts.json"
    if not cuts_file.exists():
        raise FileNotFoundError(f"캐시 없음: {cuts_file}. --skip_preprocess 전에 전처리를 먼저 실행하세요.")
    cuts = [Cut(**d) for d in _load_json(cuts_file, [])]
    print(f"    컷 수: {len(cuts)}")
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
