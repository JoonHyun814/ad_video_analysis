import json
from utils.json_utils import parse_json as _parse_json
from utils.llm_caller import call_claude
from pathlib import Path

from pipeline.cuts import Cut

_SCHEMA = (
    '{"title": "추정 광고 제목", "brand": "브랜드/제품명", "concept": "광고 핵심 컨셉 한 줄",'
    ' "narrative": "전체 서사 흐름 요약",'
    ' "cast": [{"id": "캐릭터1", "description": "외모·인상·역할 묘사"}],'
    ' "scenes": [{"cut_index": 1, "time": "0.00~3.90s",'
    ' "beats": ['
    '{"type": "background", "description": "화면 구성·배경·공간 묘사"},'
    '{"type": "camera", "description": "카메라 앵글·무브먼트"},'
    '{"type": "action", "cast": "캐릭터1", "description": "동작·움직임 묘사"},'
    '{"type": "music", "description": "음악·사운드 묘사"},'
    '{"type": "dialogue", "cast": "캐릭터1", "description": "대사 내용"},'
    '{"type": "text_overlay", "description": "화면에 표시된 텍스트"}'
    ']}],'
    ' "key_messages": ["핵심 메시지"],'
    ' "production_notes": "재제작 시 참고할 연출·기술 특이사항"}'
)


def analyze_scenario(
    cuts: list[Cut],
    frames_dir: Path,
    cut_analysis: list[dict],
    ocr_data: dict[str, list[str]],
    stt_segments: list[dict],
    audio_data: dict | None = None,
) -> dict:
    """컷분석·OCR·STT·오디오 데이터를 종합해 재제작 가능한 광고 시나리오를 생성한다."""
    duration = max((c.end_sec for c in cuts), default=0.0)
    context = _build_context(cuts, cut_analysis, ocr_data, stt_segments, audio_data)
    return _call_claude(context, duration)


# ── Context building ───────────────────────────────────────────────────────────

def _build_context(
    cuts: list[Cut],
    cut_analysis: list[dict],
    ocr_data: dict[str, list[str]],
    stt_segments: list[dict],
    audio_data: dict | None = None,
) -> str:
    parts: list[str] = []

    if stt_segments:
        stt = " / ".join(f'{s["start_sec"]:.1f}s: "{s["text"]}"' for s in stt_segments)
        parts.append(f"[음성]\n{stt}")

    if audio_data:
        audio_summary = _summarize_audio(audio_data)
        if audio_summary:
            parts.append(f"[오디오]\n{audio_summary}")

    if cut_analysis:
        cut_map = {c.index: c for c in cuts}
        lines = []
        for c in cut_analysis:
            if c.get("error"):
                continue
            cut = cut_map.get(c["cut_index"])
            line = f"컷{c['cut_index']} {c['start_sec']:.1f}~{c['end_sec']:.1f}s: {c.get('flow', '')}"
            cast = c.get("cast", "")
            if cast and cast not in ("없음", "none"):
                line += f" | 인물: {cast}"
            tf = c.get("text_flow", "")
            if tf and tf not in ("없음", "none", "없음."):
                line += f" | 텍스트흐름: {tf}"
            if cut:
                ocr = _cut_ocr(ocr_data, cut)
                if ocr:
                    line += f" | OCR: {ocr}"
            lines.append(line)
        parts.append("[컷별 흐름]\n" + "\n".join(lines))

    return "\n\n".join(parts)


_BGM_SILENCE_LUFS = -50.0


def _summarize_audio(audio_data: dict) -> str:
    """audio_analysis 결과에서 시나리오 작성에 필요한 정보만 추려 텍스트로 반환한다."""
    lines: list[str] = []

    cut_lines = []
    for c in audio_data.get("bgm", {}).get("cuts", []):
        prefix = f"  컷{c['cut_index']}({c['start_sec']:.1f}~{c['end_sec']:.1f}s): "
        lufs = c.get("loudness_lufs_integrated")
        if c.get("skipped") or lufs is None or lufs < _BGM_SILENCE_LUFS:
            cut_lines.append(prefix + "배경음악 없음")
            continue
        tags: list[str] = []
        genre = c.get("genre_tags") or []
        mood = c.get("mood_tags") or []
        if genre:
            tags.append(f"장르: {', '.join(genre)}")
        if mood:
            tags.append(f"분위기: {', '.join(mood)}")
        cut_lines.append(prefix + (" / ".join(tags) if tags else "배경음악 없음"))
    if cut_lines:
        lines.append("컷별 BGM:\n" + "\n".join(cut_lines))

    labeled = [e for e in audio_data.get("sfx", {}).get("events", []) if e.get("label")]
    if labeled:
        ev_str = ", ".join(f'{e["label"]}({e["time_sec"]:.1f}s)' for e in labeled)
        lines.append(f"SFX: {ev_str}")

    return "\n".join(lines)


def _cut_ocr(ocr_data: dict[str, list[str]], cut: Cut) -> str:
    texts: set[str] = set()
    for fname, words in ocr_data.items():
        try:
            idx = int(fname.replace("frame_", "").replace(".jpg", ""))
        except ValueError:
            continue
        if cut.start_frame <= idx <= cut.end_frame:
            texts.update(w for w in words if len(w.strip()) > 1)
    return ", ".join(f'"{t}"' for t in texts) if texts else ""


# ── Claude call ────────────────────────────────────────────────────────────────


def _call_claude(context: str, duration: float) -> dict:
    prompt = (
        "너는 광고 시나리오 전문가다. 아래 분석 데이터를 참고해 이 광고를 재제작할 수 있을 수준의 "
        "완전한 시나리오를 JSON으로 작성해라. 첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
        "규칙:\n"
        "1. cast: 컷별 흐름의 '인물' 설명을 종합해 전체 등장 인물 목록을 직접 구성한다. "
        "동일 인물은 하나의 캐릭터 ID('캐릭터1', '캐릭터2' 등)로 통합한다.\n"
        "2. scenes[].beats: 각 컷 안의 시간 순 사건을 beat 단위로 나열한다.\n"
        "   - type=background: 배경·공간 변화 묘사\n"
        "   - type=camera: 카메라 앵글·무브먼트 묘사\n"
        "   - type=action: cast에 정의된 캐릭터 ID를 cast 필드에 적고 동작 묘사 (여럿이면 '캐릭터1,캐릭터2')\n"
        "   - type=dialogue: 대사·나레이션, cast 필드에 캐릭터 ID\n"
        "   - type=music: 음악·사운드 묘사\n"
        "   - type=text_overlay: 화면에 표시된 텍스트. 없으면 beat 자체를 생략\n"
        "3. cast에 없는 캐릭터 ID를 beats에서 사용하지 않는다.\n\n"
        f"영상 길이: {round(duration, 1)}초\n\n"
        f"{context}\n\n"
        f"{_SCHEMA}"
    )
    return call_claude(prompt, timeout=600)

