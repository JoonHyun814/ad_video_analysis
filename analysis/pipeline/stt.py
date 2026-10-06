"""STT + 화자 분리: faster-whisper 전사 + NeMo MSDD 화자 배정 직접 구현."""

import subprocess
from pathlib import Path

import nltk
import torch

_SENT_END = ".?!"


def run_diarization(
    video_path: Path,
    out_dir: Path,
    language: str = "ko",
    whisper_model: str = "medium",
    device: str = "cuda",
) -> list[dict]:
    """faster-whisper STT + NeMo MSDD 화자 분리를 수행하고 세그먼트 리스트를 반환한다."""
    from pipeline.stt_nemo import diarize

    audio_path = _extract_audio(video_path, out_dir)
    words = _transcribe(audio_path, language, whisper_model, device)
    if not words:
        return []

    try:
        speaker_ts = diarize(audio_path, device)
        words = _assign_speakers(words, speaker_ts)
        words = _realign_speakers(words)
    except Exception as exc:
        print(f"      [WARN] 화자 분리 실패 ({type(exc).__name__}: {exc})")
        if device == "cuda":
            print("      [INFO] CPU로 재시도...")
            try:
                speaker_ts = diarize(audio_path, "cpu")
                words = _assign_speakers(words, speaker_ts)
                words = _realign_speakers(words)
                print("      [INFO] CPU 재시도 성공")
            except Exception as exc2:
                print(f"      [WARN] CPU 재시도 실패, Speaker 0 으로 통일: {type(exc2).__name__}: {exc2}")
                for w in words:
                    w["speaker"] = 0
        else:
            print("      [WARN] Speaker 0 으로 통일")
            for w in words:
                w["speaker"] = 0

    return _group_segments(words)


def _extract_audio(video_path: Path, out_dir: Path) -> Path:
    """ffmpeg로 영상에서 16kHz 모노 WAV를 추출한다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    audio_path = out_dir / "audio.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video_path), "-vn", "-ar", "16000", "-ac", "1", str(audio_path)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return audio_path.resolve()


def _transcribe(audio_path: Path, language: str, model_name: str, device: str) -> list[dict]:
    """faster-whisper로 단어 단위 타임스탬프를 포함한 전사를 수행한다."""
    import faster_whisper

    compute = "float16" if device == "cuda" else "int8"
    model = faster_whisper.WhisperModel(model_name, device=device, compute_type=compute)
    pipe = faster_whisper.BatchedInferencePipeline(model)
    audio = faster_whisper.decode_audio(str(audio_path))
    segs, _ = pipe.transcribe(audio, language=language, word_timestamps=True, batch_size=8)

    words = []
    for seg in segs:
        for w in (seg.words or []):
            if w.start is not None and w.end is not None:
                words.append({
                    "word": w.word,
                    "start": int(w.start * 1000),
                    "end": int(w.end * 1000),
                    "speaker": 0,
                })

    del model, pipe
    if device == "cuda":
        torch.cuda.empty_cache()
        torch.cuda.synchronize()  # CUDA 작업 완료 후 cuSOLVER 컨텍스트 충돌 방지
    return words


def _assign_speakers(words: list[dict], speaker_ts: list[tuple]) -> list[dict]:
    """각 단어에 화자 레이블을 할당한다."""
    if not speaker_ts:
        return words
    idx = 0
    s, e, sp = speaker_ts[0]
    for w in words:
        while w["start"] > e and idx < len(speaker_ts) - 1:
            idx += 1
            s, e, sp = speaker_ts[idx]
        w["speaker"] = sp
    return words


def _realign_speakers(words: list[dict], max_words: int = 50) -> list[dict]:
    """문장 경계에서 화자가 바뀌는 경우 다수결로 조정한다."""
    spk = [w["speaker"] for w in words]
    txt = [w["word"] for w in words]
    k = 0
    while k < len(words) - 1:
        if spk[k] != spk[k + 1] and not (txt[k] and txt[k][-1] in _SENT_END):
            li, ri = _sent_bounds(k, txt, spk, max_words)
            if li != -1 and ri != -1:
                chunk = spk[li: ri + 1]
                maj = max(set(chunk), key=chunk.count)
                if chunk.count(maj) >= len(chunk) // 2:
                    spk[li: ri + 1] = [maj] * (ri - li + 1)
                    k = ri
        k += 1
    for i, w in enumerate(words):
        w["speaker"] = spk[i]
    return words


def _sent_bounds(k: int, txt: list[str], spk: list[int], max_w: int) -> tuple[int, int]:
    """단어 k를 포함하는 문장의 시작·끝 인덱스를 반환한다. 불명확하면 (-1, -1)."""
    li = k
    while li > 0 and k - li < max_w and spk[li - 1] == spk[li] and not (txt[li - 1] and txt[li - 1][-1] in _SENT_END):
        li -= 1
    li = li if li == 0 or (txt[li - 1] and txt[li - 1][-1] in _SENT_END) else -1

    ri = k
    while ri < len(txt) - 1 and ri - k < max_w and not (txt[ri] and txt[ri][-1] in _SENT_END):
        ri += 1
    ri = ri if ri == len(txt) - 1 or (txt[ri] and txt[ri][-1] in _SENT_END) else -1
    return li, ri


def _group_segments(words: list[dict]) -> list[dict]:
    """연속된 같은 화자의 단어를 문장 단위로 묶어 세그먼트 리스트로 반환한다."""
    try:
        sent_break = nltk.tokenize.PunktSentenceTokenizer().text_contains_sentbreak
    except Exception:
        sent_break = lambda t: bool(t) and t.rstrip()[-1:] in _SENT_END

    segments: list[dict] = []
    cur_spk = f"Speaker {words[0]['speaker']}"
    cur_s, cur_e, cur_text = words[0]["start"], words[0]["end"], ""

    for w in words:
        spk = f"Speaker {w['speaker']}"
        if spk != cur_spk or sent_break(cur_text + " " + w["word"]):
            if cur_text.strip():
                segments.append({"speaker": cur_spk, "start_sec": round(cur_s / 1000, 3),
                                  "end_sec": round(cur_e / 1000, 3), "text": cur_text.strip()})
            cur_spk, cur_s, cur_text = spk, w["start"], ""
        cur_e = w["end"]
        cur_text += w["word"] + " "

    if cur_text.strip():
        segments.append({"speaker": cur_spk, "start_sec": round(cur_s / 1000, 3),
                          "end_sec": round(cur_e / 1000, 3), "text": cur_text.strip()})
    return segments
