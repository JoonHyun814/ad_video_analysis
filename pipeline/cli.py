import argparse
import dataclasses
import json
import shutil
from pathlib import Path

from pipeline.audio_analysis import analyze_audio
from pipeline.cut_analysis import analyze_cuts
from pipeline.cut_analysis_codex import analyze_cuts_codex
from pipeline.cuts import detect_cuts, merge_to_max_cuts
from pipeline.frames import extract_frames_at_fps
from pipeline.keyframe import extract_keyframes
from pipeline.ocr import run_ocr_batch
from pipeline.scenario_analysis import analyze_scenario
from pipeline.scenario_analysis_codex import analyze_scenario_codex
from pipeline.scene_analysis import analyze_keyframes
from pipeline.scene_analysis_codex import analyze_keyframes_codex
from pipeline.stt import run_diarization
from pipeline.video_loader import get_video_info

_OUTPUT_ROOT = Path("output")
_CUT_BACKENDS = ("transnetv2", "scenedetect")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="영상 분석 파이프라인 (컷 감지 → keyframe → frames → OCR)")
    parser.add_argument("--video_id", type=int, required=True, help="video_uploads.id")
    parser.add_argument(
        "--cut_backend",
        choices=_CUT_BACKENDS,
        default="transnetv2",
        help="컷 감지 백엔드 (기본: transnetv2)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="컷 감지 민감도 (transnetv2: 0.3 기본, scenedetect: 27.0 기본)",
    )
    parser.add_argument(
        "--max_cuts",
        type=int,
        default=None,
        help="결과로 사용할 최대 컷 수 (기본: 전체)",
    )
    parser.add_argument(
        "--out_dir",
        type=Path,
        default=None,
        help=f"결과 저장 루트 디렉토리. <video_id> 가 자동으로 하위 폴더로 추가됨 (기본: {_OUTPUT_ROOT})",
    )
    parser.add_argument(
        "--llm_backend",
        choices=("claude", "codex"),
        default="claude",
        help="LLM 분석 백엔드 — scene/cut/cast/scenario 전체 적용 (기본: claude)",
    )
    parser.add_argument(
        "--skip_scene_analysis",
        action="store_true",
        help="scene_analysis 단계를 건너뜀. 기존 scene_analysis.json 이 있으면 삭제하지 않고 유지",
    )
    parser.add_argument(
        "--skip_cut_analysis",
        action="store_true",
        help="cut_analysis 단계를 건너뜀. 기존 cut_analysis.json 이 있으면 삭제하지 않고 유지",
    )
    parser.add_argument(
        "--skip_scenario_analysis",
        action="store_true",
        help="scenario_analysis 단계를 건너뜀. 기존 scenario_analysis.json 이 있으면 삭제하지 않고 유지",
    )
    return parser


def _detect(video_path: Path, backend: str, threshold: float | None, max_cuts: int | None) -> list:
    if backend == "transnetv2":
        from pipeline.transnetv2_cuts import detect_cuts_transnetv2

        thr = threshold if threshold is not None else 0.3
        cuts = detect_cuts_transnetv2(video_path, threshold=thr)
    else:
        thr = threshold if threshold is not None else 27.0
        cuts = detect_cuts(video_path, threshold=thr)

    return merge_to_max_cuts(cuts, max_cuts) if max_cuts is not None else cuts


def main() -> None:
    args = _build_parser().parse_args()
    base = args.out_dir if args.out_dir is not None else _OUTPUT_ROOT
    out = base / str(args.video_id)

    if out.exists():
        _clean_out_dir(out, args.skip_scene_analysis, args.skip_cut_analysis, args.skip_scenario_analysis)
        print(f"      기존 결과 삭제: {out}")

    print(f"[1/10] 영상 정보 조회 중... (video_id={args.video_id})")
    video_path, meta = get_video_info(args.video_id)
    print(f"      파일: {video_path}")

    print(f"[2/10] 컷 감지 중... (backend={args.cut_backend}, threshold={args.threshold}, max_cuts={args.max_cuts})")
    cuts = _detect(video_path, args.cut_backend, args.threshold, args.max_cuts)
    _save_json(out / "cuts.json", [dataclasses.asdict(c) for c in cuts])
    print(f"      컷 수: {len(cuts)}  →  {out / 'cuts.json'}")

    print("[3/10] Keyframe 추출 중...")
    keyframes = extract_keyframes(video_path, cuts, out / "keyframes")
    print(f"      추출된 keyframe: {len(keyframes)}장  →  {out / 'keyframes'}")

    print("[4/10] Frames 추출 중... (fps=2)")
    frames = extract_frames_at_fps(video_path, out / "frames", fps=2.0)
    print(f"      추출된 frames: {len(frames)}장  →  {out / 'frames'}")

    print("[5/10] OCR 진행 중... (전체 frames 기준)")
    ocr_results = run_ocr_batch(frames)
    _save_json(out / "ocr.json", ocr_results)
    print(f"      완료  →  {out / 'ocr.json'}")

    print("[6/10] STT + 화자 분리 중... (whisper-diarization)")
    stt_segments = run_diarization(video_path, out / "stt")
    _save_json(out / "stt.json", stt_segments)
    print(f"      세그먼트 수: {len(stt_segments)}  →  {out / 'stt.json'}")

    print("[7/10] BGM + SFX 분석 중...")
    audio_result = analyze_audio(video_path, cuts)
    _save_json(out / "audio_analysis.json", audio_result)
    print(f"      완료  →  {out / 'audio_analysis.json'}")

    llm = args.llm_backend

    if args.skip_scene_analysis:
        print("[8/10] Scene 분석 생략 (--skip_scene_analysis)")
    elif llm == "codex":
        print(f"[8/10] Scene 분석 중... (codex, 컷 수={len(cuts)})")
        scene_results = analyze_keyframes_codex(cuts, out / "keyframes")
        _save_json(out / "scene_analysis.json", scene_results)
        print(f"      완료  →  {out / 'scene_analysis.json'}")
    else:
        print(f"[8/10] Scene 분석 중... (claude -p, 컷 수={len(cuts)})")
        scene_results = analyze_keyframes(cuts, out / "keyframes", out)
        _save_json(out / "scene_analysis.json", scene_results)
        print(f"      완료  →  {out / 'scene_analysis.json'}")

    if args.skip_cut_analysis:
        print("[9/10] Cut 분석 생략 (--skip_cut_analysis)")
        cut_json = out / "cut_analysis.json"
        cut_results = json.loads(cut_json.read_text(encoding="utf-8")) if cut_json.exists() else []
    elif llm == "codex":
        print(f"[9/10] Cut 분석 중... (codex, 컷 수={len(cuts)})")
        cut_results = analyze_cuts_codex(cuts, out / "frames", ocr_results)
        _save_json(out / "cut_analysis.json", cut_results)
        print(f"      완료  →  {out / 'cut_analysis.json'}")
    else:
        print(f"[9/10] Cut 분석 중... (claude -p, 컷 수={len(cuts)})")
        cut_results = analyze_cuts(cuts, out / "frames", ocr_results, out)
        _save_json(out / "cut_analysis.json", cut_results)
        print(f"      완료  →  {out / 'cut_analysis.json'}")

    if args.skip_scenario_analysis:
        print("[10/10] 시나리오 분석 생략 (--skip_scenario_analysis)")
    elif llm == "codex":
        print("[10/10] 시나리오 분석 중... (codex)")
        scenario = analyze_scenario_codex(
            cuts=cuts,
            frames_dir=out / "frames",
            cut_analysis=cut_results,
            ocr_data=ocr_results,
            stt_segments=stt_segments,
            audio_data=audio_result,
        )
        _save_json(out / "scenario_analysis.json", scenario)
        print(f"      완료  →  {out / 'scenario_analysis.json'}")
    else:
        print("[10/10] 시나리오 분석 중... (claude -p)")
        scenario = analyze_scenario(
            cuts=cuts,
            frames_dir=out / "frames",
            cut_analysis=cut_results,
            ocr_data=ocr_results,
            stt_segments=stt_segments,
            audio_data=audio_result,
        )
        _save_json(out / "scenario_analysis.json", scenario)
        print(f"      완료  →  {out / 'scenario_analysis.json'}")


def _clean_out_dir(out: Path, keep_scene_analysis: bool, keep_cut_analysis: bool, keep_scenario_analysis: bool) -> None:
    files_to_keep = []
    if keep_scene_analysis:
        files_to_keep.append(out / "scene_analysis.json")
    if keep_cut_analysis:
        files_to_keep.append(out / "cut_analysis.json")
    if keep_scenario_analysis:
        files_to_keep.append(out / "scenario_analysis.json")

    if not files_to_keep:
        shutil.rmtree(out)
        return

    saved = {p: p.read_bytes() for p in files_to_keep if p.exists()}
    shutil.rmtree(out)
    if saved:
        out.mkdir(parents=True)
        for p, data in saved.items():
            p.write_bytes(data)


def _save_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
