"""pipeline.cli 전처리 1~7단계(컷 감지·keyframe·frames·OCR·STT·BGM/SFX)를 동일하게 실행하고 캐시를 읽는다.

pipeline 의 무거운 모듈(TF·easyocr·whisper 등)은 실제 전처리를 돌릴 때만 함수 안에서 불러온다."""
import dataclasses
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from pikk_tagging.results_io import save_json as _save_json

_OWN_FILES = ("cuts.json", "ocr.json", "stt.json", "audio_analysis.json", "tags.json", "proposals.json")
_OWN_DIRS = ("keyframes", "frames", "stt")


@dataclass
class Preprocessed:
    cuts: list
    ocr: dict
    stt: list
    audio: dict


def load_preprocessed(src: Path) -> Preprocessed:
    """기존 전처리 결과 폴더(pipeline 출력과 같은 구조)를 읽는다. 무거운 전처리 의존성은 불러오지 않는다."""
    from pipeline.cuts import Cut

    cuts_json = src / "cuts.json"
    if not cuts_json.exists():
        raise FileNotFoundError(f"전처리 결과 없음: {cuts_json}")
    cuts = [Cut(**d) for d in json.loads(cuts_json.read_text(encoding="utf-8"))]
    ocr = _load_optional(src / "ocr.json", {})
    stt = _load_optional(src / "stt.json", [])
    audio = _load_optional(src / "audio_analysis.json", {})
    print(f"      컷 수: {len(cuts)}, OCR: {len(ocr)}항목, STT: {len(stt)}개 세그먼트")
    return Preprocessed(cuts, ocr, stt, audio)


def _load_optional(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def run_preprocess(
    video_id: int | None,
    video_path_override: Path | None,
    out: Path,
    cut_backend: str,
    threshold: float | None,
    max_cuts: int | None,
) -> Preprocessed:
    """전처리를 실행해 out 에 저장한다. 이 모듈이 만드는 산출물만 지우고 그 외 파일은 건드리지 않는다."""
    from pipeline.cli import _detect, _flush_gpu

    _clean_own_outputs(out)
    video_path = _resolve_video(video_id, video_path_override)

    print(f"[2/7] 컷 감지 중... (backend={cut_backend}, threshold={threshold}, max_cuts={max_cuts})")
    cuts = _detect(video_path, cut_backend, threshold, max_cuts)
    _save_json(out / "cuts.json", [dataclasses.asdict(c) for c in cuts])
    print(f"      컷 수: {len(cuts)}  →  {out / 'cuts.json'}")
    _flush_gpu()

    ocr = _extract_visual(video_path, cuts, out)
    stt, audio = _extract_audio_text(video_path, cuts, out)
    return Preprocessed(cuts, ocr, stt, audio)


def _resolve_video(video_id: int | None, override: Path | None) -> Path:
    if override is not None:
        print(f"[1/7] 영상 파일 확인 중... ({override})")
        return override
    from pipeline.video_loader import get_video_info

    print(f"[1/7] 영상 정보 조회 중... (video_id={video_id})")
    video_path, _ = get_video_info(video_id)
    print(f"      파일: {video_path}")
    return video_path


def _extract_visual(video_path: Path, cuts: list, out: Path) -> dict:
    from pipeline.cli import _flush_gpu
    from pipeline.frames import extract_frames_at_fps
    from pipeline.keyframe import extract_keyframes
    from pipeline.ocr import run_ocr_batch

    print("[3/7] Keyframe 추출 중...")
    keyframes = extract_keyframes(video_path, cuts, out / "keyframes")
    print(f"      추출된 keyframe: {len(keyframes)}장  →  {out / 'keyframes'}")

    print("[4/7] Frames 추출 중... (fps=2)")
    frames = extract_frames_at_fps(video_path, out / "frames", fps=2.0)
    print(f"      추출된 frames: {len(frames)}장  →  {out / 'frames'}")

    print("[5/7] OCR 진행 중... (전체 frames 기준)")
    ocr = run_ocr_batch(frames)
    _save_json(out / "ocr.json", ocr)
    from pipeline import ocr as ocr_mod
    ocr_mod.release()
    _flush_gpu()
    return ocr


def _extract_audio_text(video_path: Path, cuts: list, out: Path) -> tuple[list, dict]:
    from pipeline.audio_analysis import analyze_audio
    from pipeline.cli import _flush_gpu
    from pipeline.stt import run_diarization

    print("[6/7] STT + 화자 분리 중... (whisper-diarization)")
    stt = run_diarization(video_path, out / "stt")
    _save_json(out / "stt.json", stt)

    print("[7/7] BGM + SFX 분석 중...")
    audio = analyze_audio(video_path, cuts)
    _save_json(out / "audio_analysis.json", audio)
    try:
        from pipeline import audio_clap
        audio_clap.release()
    except ImportError:
        pass
    _flush_gpu()
    return stt, audio


def _clean_own_outputs(out: Path) -> None:
    for name in _OWN_DIRS:
        shutil.rmtree(out / name, ignore_errors=True)
    for name in _OWN_FILES:
        (out / name).unlink(missing_ok=True)
