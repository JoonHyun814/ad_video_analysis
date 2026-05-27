import argparse
import dataclasses
import gc
import json
import os
import shutil
from pathlib import Path

# TF가 처음 임포트되기 전에 설정해야 GPU 전체 선점을 막을 수 있음
os.environ.setdefault("TF_FORCE_GPU_ALLOW_GROWTH", "true")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

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
_LLM_BACKENDS = ("claude", "codex", "qwen")
_QWEN_DEFAULT_MODEL = "unsloth/Qwen2.5-VL-7B-Instruct"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="영상 분석 파이프라인 (컷 감지 → keyframe → frames → OCR)")
    parser.add_argument("--video_id", type=int, default=None, help="video_uploads.id (단일)")
    parser.add_argument(
        "--video_ids",
        type=str,
        default=None,
        help="처리할 video_id 범위 (예: 1-10 / 1,3,5 / 1-5,7,9-12). --video_id 와 함께 사용 불가",
    )
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
        choices=_LLM_BACKENDS,
        default="claude",
        help="LLM 분석 백엔드 — scene/cut/cast/scenario 전체 적용 (기본: claude)",
    )
    parser.add_argument(
        "--lora_path",
        type=str,
        default=None,
        help="[qwen 백엔드] 학습된 LoRA 어댑터 경로. 지정하면 해당 경로에서 모델을 로드한다.",
    )
    parser.add_argument(
        "--qwen_model",
        type=str,
        default=_QWEN_DEFAULT_MODEL,
        help=f"[qwen 백엔드] lora_path 미지정 시 사용할 베이스 모델명/경로 (기본: {_QWEN_DEFAULT_MODEL})",
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
    parser.add_argument(
        "--skip_parsed_analysis",
        action="store_true",
        help="parsed_analysis 단계를 건너뜀. 기존 parsed_analysis.json 이 있으면 삭제하지 않고 유지",
    )
    parser.add_argument(
        "--skip_preprocess",
        action="store_true",
        help="전처리 단계(1~7)를 건너뜀. out_dir 내 기존 cuts.json·ocr.json·stt.json·audio_analysis.json을 재사용한다.",
    )
    parser.add_argument(
        "--cache_dir",
        type=str,
        default="/root/.cache",
        help="HuggingFace·모델 캐시 루트 경로 (기본: /root/.cache)",
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
    os.environ["HF_HOME"] = args.cache_dir

    video_ids = _parse_video_ids(args)
    llm = args.llm_backend

    if llm == "qwen":
        from pipeline import qwen_client
        qwen_client.init(model=args.qwen_model, lora_path=args.lora_path)

    for i, video_id in enumerate(video_ids, 1):
        if len(video_ids) > 1:
            print(f"\n{'─'*50}")
            print(f"  [{i}/{len(video_ids)}] video_id={video_id}")
            print(f"{'─'*50}")
        _run_video(args, video_id)

    if llm == "qwen":
        from pipeline import qwen_client
        qwen_client.release()
        _flush_gpu()


def _run_video(args: argparse.Namespace, video_id: int) -> None:
    """단일 video_id에 대한 전처리 + 분석 파이프라인을 실행한다."""
    base = args.out_dir if args.out_dir is not None else _OUTPUT_ROOT
    out = base / str(video_id)
    llm = args.llm_backend

    if args.skip_preprocess:
        print("[1-7/11] 전처리 단계 생략 (--skip_preprocess)")
        cuts, ocr_results, stt_segments, audio_result = _load_preprocess_cache(out)
    else:
        if out.exists():
            _clean_out_dir(out, args.skip_scene_analysis, args.skip_cut_analysis, args.skip_scenario_analysis)
            print(f"      기존 결과 삭제: {out}")

        print(f"[1/11] 영상 정보 조회 중... (video_id={video_id})")
        video_path, meta = get_video_info(video_id)
        print(f"      파일: {video_path}")

        print(f"[2/11] 컷 감지 중... (backend={args.cut_backend}, threshold={args.threshold}, max_cuts={args.max_cuts})")
        cuts = _detect(video_path, args.cut_backend, args.threshold, args.max_cuts)
        _save_json(out / "cuts.json", [dataclasses.asdict(c) for c in cuts])
        print(f"      컷 수: {len(cuts)}  →  {out / 'cuts.json'}")
        _flush_gpu()

        print("[3/11] Keyframe 추출 중...")
        keyframes = extract_keyframes(video_path, cuts, out / "keyframes")
        print(f"      추출된 keyframe: {len(keyframes)}장  →  {out / 'keyframes'}")

        print("[4/11] Frames 추출 중... (fps=2)")
        frames = extract_frames_at_fps(video_path, out / "frames", fps=2.0)
        print(f"      추출된 frames: {len(frames)}장  →  {out / 'frames'}")

        print("[5/11] OCR 진행 중... (전체 frames 기준)")
        ocr_results = run_ocr_batch(frames)
        _save_json(out / "ocr.json", ocr_results)
        print(f"      완료  →  {out / 'ocr.json'}")
        from pipeline import ocr as _ocr_mod
        _ocr_mod.release()
        _flush_gpu()

        print("[6/11] STT + 화자 분리 중... (whisper-diarization)")
        stt_segments = run_diarization(video_path, out / "stt")
        _save_json(out / "stt.json", stt_segments)
        print(f"      세그먼트 수: {len(stt_segments)}  →  {out / 'stt.json'}")

        print("[7/11] BGM + SFX 분석 중...")
        audio_result = analyze_audio(video_path, cuts)
        _save_json(out / "audio_analysis.json", audio_result)
        print(f"      완료  →  {out / 'audio_analysis.json'}")
        try:
            from pipeline import audio_clap as _clap_mod
            _clap_mod.release()
        except ImportError:
            pass
        _flush_gpu()

    scene_results: list = []
    scenario: dict = {}

    if args.skip_scene_analysis:
        scene_json = out / "scene_analysis.json"
        if scene_json.exists():
            scene_results = json.loads(scene_json.read_text(encoding="utf-8"))
        print("[8/11] Scene 분석 생략 (--skip_scene_analysis)")
    elif llm == "codex":
        print(f"[8/11] Scene 분석 중... (codex, 컷 수={len(cuts)})")
        scene_results = analyze_keyframes_codex(cuts, out / "keyframes")
        _save_json(out / "scene_analysis.json", scene_results)
        print(f"      완료  →  {out / 'scene_analysis.json'}")
    elif llm == "qwen":
        from pipeline.scene_analysis_qwen import analyze_keyframes_qwen
        print(f"[8/11] Scene 분석 중... (qwen, 컷 수={len(cuts)})")
        scene_results = analyze_keyframes_qwen(cuts, out / "keyframes")
        _save_json(out / "scene_analysis.json", scene_results)
        print(f"      완료  →  {out / 'scene_analysis.json'}")
    else:
        print(f"[8/11] Scene 분석 중... (claude -p, 컷 수={len(cuts)})")
        scene_results = analyze_keyframes(cuts, out / "keyframes", out)
        _save_json(out / "scene_analysis.json", scene_results)
        print(f"      완료  →  {out / 'scene_analysis.json'}")

    if args.skip_cut_analysis:
        print("[9/11] Cut 분석 생략 (--skip_cut_analysis)")
        cut_json = out / "cut_analysis.json"
        cut_results = json.loads(cut_json.read_text(encoding="utf-8")) if cut_json.exists() else []
    elif llm == "codex":
        print(f"[9/11] Cut 분석 중... (codex, 컷 수={len(cuts)})")
        cut_results = analyze_cuts_codex(cuts, out / "frames", ocr_results)
        _save_json(out / "cut_analysis.json", cut_results)
        print(f"      완료  →  {out / 'cut_analysis.json'}")
    elif llm == "qwen":
        from pipeline.cut_analysis_qwen import analyze_cuts_qwen
        print(f"[9/11] Cut 분석 중... (qwen, 컷 수={len(cuts)})")
        cut_results = analyze_cuts_qwen(cuts, out / "frames", ocr_results)
        _save_json(out / "cut_analysis.json", cut_results)
        print(f"      완료  →  {out / 'cut_analysis.json'}")
    else:
        print(f"[9/11] Cut 분석 중... (claude -p, 컷 수={len(cuts)})")
        cut_results = analyze_cuts(cuts, out / "frames", ocr_results, out)
        _save_json(out / "cut_analysis.json", cut_results)
        print(f"      완료  →  {out / 'cut_analysis.json'}")

    if args.skip_scenario_analysis:
        scenario_json = out / "scenario_analysis.json"
        if scenario_json.exists():
            scenario = json.loads(scenario_json.read_text(encoding="utf-8"))
        print("[10/11] 시나리오 분석 생략 (--skip_scenario_analysis)")
    elif llm == "codex":
        print("[10/11] 시나리오 분석 중... (codex)")
        scenario = analyze_scenario_codex(cuts=cuts, frames_dir=out / "frames", cut_analysis=cut_results, ocr_data=ocr_results, stt_segments=stt_segments, audio_data=audio_result)
        _save_json(out / "scenario_analysis.json", scenario)
        print(f"      완료  →  {out / 'scenario_analysis.json'}")
    elif llm == "qwen":
        from pipeline.scenario_analysis_qwen import analyze_scenario_qwen
        print("[10/11] 시나리오 분석 중... (qwen)")
        scenario = analyze_scenario_qwen(cuts=cuts, frames_dir=out / "frames", cut_analysis=cut_results, ocr_data=ocr_results, stt_segments=stt_segments, audio_data=audio_result)
        _save_json(out / "scenario_analysis.json", scenario)
        print(f"      완료  →  {out / 'scenario_analysis.json'}")
    else:
        print("[10/11] 시나리오 분석 중... (claude -p)")
        scenario = analyze_scenario(cuts=cuts, frames_dir=out / "frames", cut_analysis=cut_results, ocr_data=ocr_results, stt_segments=stt_segments, audio_data=audio_result)
        _save_json(out / "scenario_analysis.json", scenario)
        print(f"      완료  →  {out / 'scenario_analysis.json'}")

    if args.skip_parsed_analysis:
        print("[11/11] Parsed 분석 생략 (--skip_parsed_analysis)")
    elif llm == "codex":
        from pipeline.parsed_analysis_codex import analyze_parsed_codex
        print("[11/11] Parsed 분석 중... (codex)")
        parsed = analyze_parsed_codex(scenario=scenario, cuts=cuts, cut_analysis=cut_results, scene_analysis=scene_results, stt_segments=stt_segments, audio_data=audio_result)
        _save_json(out / "parsed_analysis.json", parsed)
        print(f"      완료  →  {out / 'parsed_analysis.json'}")
    elif llm == "qwen":
        from pipeline.parsed_analysis_qwen import analyze_parsed_qwen
        print("[11/11] Parsed 분석 중... (qwen)")
        parsed = analyze_parsed_qwen(scenario=scenario, cuts=cuts, cut_analysis=cut_results, scene_analysis=scene_results, stt_segments=stt_segments, audio_data=audio_result)
        _save_json(out / "parsed_analysis.json", parsed)
        print(f"      완료  →  {out / 'parsed_analysis.json'}")
    else:
        from pipeline.parsed_analysis import analyze_parsed
        print("[11/11] Parsed 분석 중... (claude -p)")
        parsed = analyze_parsed(scenario=scenario, cuts=cuts, cut_analysis=cut_results, scene_analysis=scene_results, stt_segments=stt_segments, audio_data=audio_result)
        _save_json(out / "parsed_analysis.json", parsed)
        print(f"      완료  →  {out / 'parsed_analysis.json'}")


def _parse_video_ids(args: argparse.Namespace) -> list[int]:
    """--video_id / --video_ids 인자를 정수 목록으로 변환한다."""
    if args.video_id is not None and args.video_ids is not None:
        raise SystemExit("오류: --video_id 와 --video_ids 는 동시에 사용할 수 없습니다.")
    if args.video_ids:
        return _expand_id_range(args.video_ids)
    if args.video_id is not None:
        return [args.video_id]
    raise SystemExit("오류: --video_id 또는 --video_ids 를 지정하세요.")


def _expand_id_range(spec: str) -> list[int]:
    """'1-5,7,9-12' 형식의 문자열을 정수 목록으로 변환한다."""
    ids: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            ids.extend(range(int(a), int(b) + 1))
        else:
            ids.append(int(part))
    return ids


def _load_preprocess_cache(out: Path) -> tuple:
    """기존 전처리 결과를 로드해 (cuts, ocr_results, stt_segments, audio_result) 를 반환한다."""
    from pipeline.cuts import Cut

    cuts_json = out / "cuts.json"
    if not cuts_json.exists():
        raise FileNotFoundError(
            f"전처리 캐시 없음: {cuts_json}\n--skip_preprocess 사용 전에 전처리를 먼저 실행하세요."
        )

    cuts = [Cut(**d) for d in json.loads(cuts_json.read_text(encoding="utf-8"))]

    def _load(name: str, default):
        p = out / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default

    ocr_results = _load("ocr.json", {})
    stt_segments = _load("stt.json", [])
    audio_result = _load("audio_analysis.json", {})

    print(f"      컷 수: {len(cuts)}, OCR: {len(ocr_results)}항목, STT: {len(stt_segments)}개 세그먼트")
    return cuts, ocr_results, stt_segments, audio_result


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


def _flush_gpu() -> None:
    """GC 수행 후 GPU 캐시를 비운다. CUDA 미사용 환경에서도 안전하게 동작한다."""
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def _save_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
