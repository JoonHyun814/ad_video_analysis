"""CLAP 기반 BGM 장르 태깅 및 SFX 이벤트 분류."""
from __future__ import annotations

import numpy as np

_GENRE_LABELS = [
    "K-pop", "pop music", "hip-hop music", "R&B soul music",
    "electronic dance music EDM", "rock music", "indie pop",
    "acoustic guitar folk music", "jazz music", "classical orchestral music",
    "ambient electronic music", "ballad love song",
    "cinematic film score", "advertising jingle commercial music",
]

_MOOD_LABELS = [
    "energetic exciting music", "upbeat cheerful happy music",
    "calm relaxing peaceful music", "dramatic intense powerful music",
    "romantic emotional heartfelt music", "inspirational motivational music",
    "playful fun lighthearted music", "melancholic sad music",
    "suspenseful tense music",
]

_SFX_LABELS: dict[str, str] = {
    "drum hit percussion beat": "드럼 히트",
    "snare drum rimshot": "스네어 드럼",
    "cymbal crash hi-hat": "심벌즈",
    "bass drum kick": "베이스 킥",
    "hand clap sound": "박수/클랩",
    "bell chime ding": "벨 차임",
    "electronic beep notification alert": "전자 알림음",
    "whoosh swoosh transition sound effect": "전환 효과음",
    "impact thud punch sound": "충격음",
    "click tap snap": "클릭/탭",
    "shaker tambourine rhythm": "쉐이커/탬버린",
    "vocal chop voice effect": "보컬 효과음",
    "synthesizer stab accent": "신스 스탭",
    "rising build up sweep": "라이징 빌드업",
    "ambient background texture": "배경 텍스처",
}

_model = None
_processor = None


def _get_clap():
    global _model, _processor
    if _model is None:
        import torch
        from transformers import ClapModel, ClapProcessor
        _processor = ClapProcessor.from_pretrained("laion/clap-htsat-unfused")
        _model = ClapModel.from_pretrained("laion/clap-htsat-unfused")
        _model.eval()
    return _model, _processor


def release() -> None:
    """CLAP 모델을 메모리에서 해제한다."""
    global _model, _processor
    _model = None
    _processor = None


_CLAP_SR = 48000


def _audio_features(audios: list[np.ndarray], sr: int):
    import librosa
    import torch
    import torch.nn.functional as F
    model, processor = _get_clap()
    if sr != _CLAP_SR:
        audios = [librosa.resample(y, orig_sr=sr, target_sr=_CLAP_SR) for y in audios]
        sr = _CLAP_SR
    inputs = processor(audios=audios, sampling_rate=sr, return_tensors="pt")
    with torch.no_grad():
        return F.normalize(model.get_audio_features(**inputs), dim=-1)


def _text_features(texts: list[str]):
    import torch
    import torch.nn.functional as F
    model, processor = _get_clap()
    inputs = processor(text=texts, return_tensors="pt", padding=True)
    with torch.no_grad():
        return F.normalize(model.get_text_features(**inputs), dim=-1)


def tag_bgm_genre(y: np.ndarray, sr: int) -> dict:
    """BGM 장르 태그(top-3)와 무드 태그(top-3)를 반환한다."""
    return tag_bgm_genre_batch([y], sr)[0]


def tag_bgm_genre_batch(ys: list[np.ndarray], sr: int) -> list[dict]:
    """여러 오디오 구간의 장르·무드 태그를 한 번의 CLAP 추론으로 반환한다."""
    a = _audio_features(ys, sr)
    genre_sims = a @ _text_features(_GENRE_LABELS).T
    mood_sims = a @ _text_features(_MOOD_LABELS).T
    results = []
    for i in range(len(ys)):
        results.append({
            "genre_tags": [_GENRE_LABELS[j] for j in genre_sims[i].topk(3).indices.tolist()],
            "mood_tags": [_MOOD_LABELS[j] for j in mood_sims[i].topk(3).indices.tolist()],
        })
    return results


def classify_sfx_events(
    y: np.ndarray, sr: int, events: list[dict],
) -> tuple[list[dict], str]:
    """각 SFX 이벤트를 CLAP으로 분류하고 한국어 요약 문장을 생성한다."""
    if not events:
        return [], "감지된 효과음 없음"

    labels_en = list(_SFX_LABELS.keys())
    win = max(int(sr), 512)

    windows: list[np.ndarray] = []
    for ev in events:
        c = int(ev["time_sec"] * sr)
        s, e = max(0, c - win // 2), min(len(y), c + win // 2)
        chunk = y[s:e]
        if len(chunk) < win:
            chunk = np.pad(chunk, (0, win - len(chunk)))
        windows.append(chunk)

    sims = _audio_features(windows, sr) @ _text_features(labels_en).T

    labeled: list[dict] = []
    counts: dict[str, int] = {}
    for i, ev in enumerate(events):
        ko = _SFX_LABELS[labels_en[int(sims[i].argmax())]]
        counts[ko] = counts.get(ko, 0) + 1
        labeled.append({
            "time_sec": ev["time_sec"],
            "label": ko,
            "peak_energy_dbfs": ev["peak_energy_dbfs"],
        })

    return labeled, _build_summary(labeled, counts)


def _build_summary(events: list[dict], counts: dict[str, int]) -> str:
    dominant = sorted(counts.items(), key=lambda x: -x[1])[:3]
    parts = ", ".join(f"{k}({v}회)" for k, v in dominant)
    times = sorted(e["time_sec"] for e in events)
    span = f"{times[0]:.1f}~{times[-1]:.1f}초"
    return f"총 {len(events)}개 음향 이벤트 감지 ({span}). 주요 효과음: {parts}."
