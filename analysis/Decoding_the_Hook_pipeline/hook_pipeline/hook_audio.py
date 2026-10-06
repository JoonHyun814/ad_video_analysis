"""훅 구간 오디오 추출(ffmpeg) + ASR(faster-whisper). 논문 3.2: 음성이 있으면 ASR 로 텍스트화한다."""
import subprocess
from pathlib import Path

_SAMPLE_RATE = 22050  # librosa 기본 샘플레이트
_asr_model = None


def extract_hook_audio(video_path: Path, hook_sec: float, out_path: Path) -> Path | None:
    """첫 hook_sec 초를 모노 WAV 로 저장한다. 오디오 트랙이 없으면 None."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(video_path), "-t", str(hook_sec), "-vn",
         "-ac", "1", "-ar", str(_SAMPLE_RATE), str(out_path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0 or not out_path.exists() or out_path.stat().st_size <= 44:
        return None
    return out_path


def transcribe(audio_path: Path, model_name: str, language: str | None) -> dict:
    """훅 구간 발화를 전사한다. 발화가 없으면 text 가 빈 문자열."""
    model = _load_asr(model_name)
    segments, info = model.transcribe(str(audio_path), language=language, vad_filter=True)
    segs = [{"start_sec": round(s.start, 3), "end_sec": round(s.end, 3), "text": s.text.strip()} for s in segments]
    return {"language": info.language, "text": " ".join(s["text"] for s in segs).strip(), "segments": segs}


def _load_asr(model_name: str):
    global _asr_model
    if _asr_model is None:
        import faster_whisper
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute = "float16" if device == "cuda" else "int8"
        _asr_model = faster_whisper.WhisperModel(model_name, device=device, compute_type=compute)
    return _asr_model


def release_asr() -> None:
    """배치 종료 시 Whisper 모델을 내려 GPU 메모리를 비운다."""
    global _asr_model
    _asr_model = None
    import gc

    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass
