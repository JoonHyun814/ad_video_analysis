import subprocess
import tempfile
from pathlib import Path

import numpy as np

from pipeline.cuts import Cut

_SR = 22050

# Krumhansl-Schmuckler key profiles
_KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
_NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def analyze_audio(video_path: Path, cuts: list[Cut]) -> dict:
    """전체 영상 오디오에서 BGM(전체·컷별) 피처·장르 태그와 SFX 이벤트를 분석한다."""
    with tempfile.TemporaryDirectory() as tmp:
        audio_path = Path(tmp) / "audio.wav"
        _extract_audio(video_path, audio_path)
        y, sr = _load(audio_path)

    bgm_overall = _bgm_features(y, sr)
    bgm_cuts = _per_cut_bgm(y, sr, cuts)
    raw_events = _sfx_events(y, sr)

    try:
        from pipeline.audio_clap import classify_sfx_events, tag_bgm_genre, tag_bgm_genre_batch
        bgm_overall.update(tag_bgm_genre(y, sr))
        _attach_clap_tags(y, sr, cuts, bgm_cuts, tag_bgm_genre_batch)
        sfx_events, sfx_summary = classify_sfx_events(y, sr, raw_events)
    except Exception as exc:
        print(f"      [WARN] CLAP 분석 실패: {exc}")
        sfx_events = raw_events
        sfx_summary = f"CLAP 분석 불가: {exc}"

    return {
        "bgm": {"overall": bgm_overall, "cuts": bgm_cuts},
        "sfx": {"summary": sfx_summary, "events": sfx_events},
    }


def _slice_audio(y: np.ndarray, sr: int, cut: Cut) -> np.ndarray:
    s = max(0, int(cut.start_sec * sr))
    e = min(len(y), int(cut.end_sec * sr))
    return y[s:e]


def _per_cut_bgm(y: np.ndarray, sr: int, cuts: list[Cut]) -> list[dict]:
    results = []
    for cut in cuts:
        y_cut = _slice_audio(y, sr, cut)
        dur = round(len(y_cut) / sr, 2)
        base = {"cut_index": cut.index, "start_sec": cut.start_sec,
                "end_sec": cut.end_sec, "duration_sec": dur}
        if dur < 0.5:
            results.append({**base, "skipped": True})
        else:
            results.append({**base, **_bgm_features(y_cut, sr)})
    return results


def _attach_clap_tags(
    y: np.ndarray, sr: int, cuts: list[Cut],
    cut_results: list[dict], tag_fn,
) -> None:
    """유효한 컷에 대해 CLAP 태그를 배치로 계산해 cut_results에 in-place 추가한다."""
    valid = [(i, c) for i, c in enumerate(cuts) if not cut_results[i].get("skipped")]
    if not valid:
        return
    ys = [_slice_audio(y, sr, c) for _, c in valid]
    tags = tag_fn(ys, sr)
    for (i, _), t in zip(valid, tags):
        cut_results[i].update(t)


def _extract_audio(video_path: Path, out: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video_path),
         "-vn", "-ar", str(_SR), "-ac", "1", str(out)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def _load(audio_path: Path) -> tuple[np.ndarray, int]:
    import soundfile as sf
    y, sr = sf.read(str(audio_path), dtype="float32")
    return (y.mean(axis=1) if y.ndim > 1 else y), sr


def _bgm_features(y: np.ndarray, sr: int) -> dict:
    import librosa
    import pyloudnorm as pyln

    key, scale, strength = _key_scale(y, sr)
    tempo = _tempo(y, sr)
    dance = _danceability(y, sr, tempo)
    dyn = _dynamic_complexity(y, sr)
    lufs = _loudness(y, sr, pyln)
    peak = float(np.max(np.abs(y))) if len(y) else 0.0
    peak_db = round(20 * np.log10(peak), 2) if peak > 0 else None

    return {
        "key": key,
        "scale": scale,
        "key_strength": strength,
        "tempo_bpm": tempo,
        "danceability": dance,
        "dynamic_complexity_db": dyn,
        "loudness_lufs_integrated": lufs,
        "true_peak_dbfs": peak_db,
    }


def _key_scale(y: np.ndarray, sr: int) -> tuple[str, str, float]:
    import librosa
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr).mean(axis=1)
    if chroma.sum() == 0:
        return "C", "major", 0.0

    def corrs(profile: np.ndarray) -> np.ndarray:
        return np.array([np.corrcoef(chroma, np.roll(profile, i))[0, 1] for i in range(12)])

    mj, mn = corrs(_KS_MAJOR), corrs(_KS_MINOR)
    if mj.max() >= mn.max():
        idx, scale, strength = int(mj.argmax()), "major", float(mj.max())
    else:
        idx, scale, strength = int(mn.argmax()), "minor", float(mn.max())
    return _NOTES[idx], scale, round(max(strength, 0.0), 4)


def _tempo(y: np.ndarray, sr: int) -> float:
    import librosa
    t, _ = librosa.beat.beat_track(y=y, sr=sr)
    t = float(t[0]) if hasattr(t, "__len__") and len(t) else float(t)
    return round(t, 1)


def _danceability(y: np.ndarray, sr: int, tempo: float) -> float:
    import librosa
    try:
        _, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
        if len(beats) < 2 or tempo <= 0:
            return 0.0
        iv = np.diff(beats)
        consistency = float(np.clip(1 - iv.std() / iv.mean(), 0, 1))
        onset_str = float(np.clip(librosa.onset.onset_strength(y=y, sr=sr).mean() / 5, 0, 1))
        tempo_score = float(np.clip(1 - abs(tempo - 115) / 60, 0, 1))
        return round(0.5 * consistency + 0.3 * onset_str + 0.2 * tempo_score, 4)
    except Exception:
        return 0.0


def _dynamic_complexity(y: np.ndarray, sr: int) -> float:
    import librosa
    rms = librosa.feature.rms(y=y)[0]
    db = 20 * np.log10(np.maximum(rms, 1e-9))
    return round(float(np.mean(np.abs(db - db.mean()))), 3)


def _loudness(y: np.ndarray, sr: int, pyln) -> float | None:
    if len(y) < int(0.5 * sr):
        return None
    try:
        lufs = float(pyln.Meter(sr).integrated_loudness(y))
        return round(lufs, 2) if np.isfinite(lufs) else None
    except Exception:
        return None


def _sfx_events(y: np.ndarray, sr: int) -> list[dict]:
    """librosa onset detection으로 주요 음향 이벤트를 추출한다."""
    import librosa
    hop = 512
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    times = librosa.times_like(onset_env, sr=sr, hop_length=hop)
    frames = librosa.onset.onset_detect(
        onset_envelope=onset_env, sr=sr, hop_length=hop, units="frames",
        pre_max=3, post_max=3, pre_avg=3, post_avg=5, delta=0.3, wait=10,
    )
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop)[0]

    events = []
    for f in frames:
        s = max(0, f * hop - hop)
        e = min(len(y), f * hop + hop * 2)
        chunk = y[s:e]
        if not len(chunk):
            continue
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        if rms < 1e-5:
            continue
        events.append({
            "time_sec": round(float(times[f]), 2),
            "peak_energy_dbfs": round(20 * np.log10(rms), 1),
            "spectral_centroid_hz": round(float(centroid[min(f, len(centroid) - 1)]), 0),
        })
    return events
