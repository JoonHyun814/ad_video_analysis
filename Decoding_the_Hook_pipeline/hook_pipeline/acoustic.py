"""논문 3.4 Audio Attributes Extractor — librosa 로 훅 구간 음향 피처 10종을 계산한다.

dB, jitter, tempo, DDP, pitch(max/min/mean), power, peak, shimmer.
jitter/shimmer/DDP 는 Praat 정의(주기·진폭의 연속 차이)를 pyin 프레임 단위 f0 와 RMS 진폭에 적용한 근사값이다.
"""
from pathlib import Path

import librosa
import numpy as np

FEATURE_NAMES = (
    "db", "jitter", "tempo", "ddp", "pitch_max", "pitch_min", "pitch_mean", "power", "peak", "shimmer",
)
_FRAME = 2048
_HOP = 512


def extract_acoustic_features(audio_path: Path | None) -> dict[str, float | None]:
    """오디오가 없거나 완전 무음이면 모든 값이 None 인 dict 를 반환한다."""
    empty = dict.fromkeys(FEATURE_NAMES)
    if audio_path is None:
        return empty
    y, sr = librosa.load(str(audio_path), sr=None, mono=True)
    if y.size < _FRAME or float(np.max(np.abs(y))) == 0.0:
        return empty
    rms = librosa.feature.rms(y=y, frame_length=_FRAME, hop_length=_HOP)[0]
    feats = {
        "db": float(np.mean(librosa.amplitude_to_db(rms, ref=1.0))),
        "tempo": _tempo(y, sr),
        "power": float(np.mean(y ** 2)),
        "peak": float(np.max(np.abs(y))),
    }
    feats.update(_pitch_features(y, sr, rms))
    return {name: feats.get(name) for name in FEATURE_NAMES}


def _tempo(y: np.ndarray, sr: int) -> float:
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr, hop_length=_HOP)
    return float(np.atleast_1d(tempo)[0])


def _pitch_features(y: np.ndarray, sr: int, rms: np.ndarray) -> dict[str, float | None]:
    f0, voiced, _ = librosa.pyin(
        y, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C7"),
        sr=sr, frame_length=_FRAME, hop_length=_HOP,
    )
    mask = voiced & ~np.isnan(f0)
    f0v = f0[mask]
    if f0v.size == 0:
        return {"pitch_max": None, "pitch_min": None, "pitch_mean": None,
                "jitter": None, "ddp": None, "shimmer": None}
    periods = 1.0 / f0v
    amps = rms[: mask.size][mask[: rms.size]]
    return {
        "pitch_max": float(np.max(f0v)),
        "pitch_min": float(np.min(f0v)),
        "pitch_mean": float(np.mean(f0v)),
        "jitter": _relative_diff(periods, order=1),
        "ddp": _relative_diff(periods, order=2),
        "shimmer": _relative_diff(amps, order=1),
    }


def _relative_diff(values: np.ndarray, order: int) -> float | None:
    """mean(|Δ^order x|) / mean(x). order=1 → local jitter/shimmer, order=2 → DDP."""
    if values.size <= order or float(np.mean(values)) == 0.0:
        return None
    return float(np.mean(np.abs(np.diff(values, n=order))) / np.mean(values))
