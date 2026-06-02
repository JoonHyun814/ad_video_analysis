"""얼굴 크롭 이미지를 Gemini Vision으로 분석해 cast 리스트를 생성한다."""
import json
import re
from pathlib import Path

from pipeline.cast_analysis import _save_face_crops
from pipeline.cuts import Cut
from utils.gemini_caller import DEFAULT_MODEL, call_gemini_with_images_raw

_SCHEMA = '[{"id": "캐릭터1", "description": "외모·인상·역할을 구체적으로 묘사"}]'


def analyze_cast_gemini(
    cuts: list[Cut],
    frames_dir: Path,
    face_detection: dict[str, list[dict]],
    cut_analysis: list[dict],
    out_dir: Path,
    model: str = DEFAULT_MODEL,
) -> list[dict]:
    """얼굴 크롭 + cut_analysis를 Gemini Vision으로 분석해 등장 인물 cast 리스트를 반환한다."""
    face_crops = _save_face_crops(frames_dir, cuts, face_detection, out_dir)
    if not face_crops:
        return []
    hints = _cut_hints(cut_analysis)
    return _call_gemini(face_crops, hints, model)


def _cut_hints(cut_analysis: list[dict]) -> str:
    lines = []
    for c in cut_analysis:
        if c.get("error"):
            continue
        subj = c.get("subjects", "")
        lines.append(f"컷{c['cut_index']} {c['start_sec']:.1f}~{c['end_sec']:.1f}s: {subj}")
    return "\n".join(lines)


def _call_gemini(
    face_crops: list[tuple[Path, str]],
    hints: str,
    model: str,
) -> list[dict]:
    prompt = (
        "너는 광고 캐스팅 분석 전문가다. 첨부된 얼굴 이미지와 컷별 등장 인물 힌트를 참고해 "
        "이 광고에 등장하는 모든 인물을 파악하고 cast 리스트를 JSON 배열로 작성해라. "
        "첫 글자가 반드시 '['여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
        "규칙:\n"
        "1. 동일 인물이 여러 컷에 등장하면 하나의 캐릭터 ID로 통합한다.\n"
        "2. 각 인물에 '캐릭터1', '캐릭터2' 등 순번 ID를 부여한다.\n"
        "3. description에는 외모·인상·역할을 구체적으로 묘사한다.\n\n"
        f"[컷별 등장 인물 힌트]\n{hints}\n\n"
        f"{_SCHEMA}"
    )
    image_paths = [p for p, _ in face_crops]
    text = call_gemini_with_images_raw(prompt, image_paths, model=model, timeout=300)
    return _parse_list(text)


def _parse_list(text: str) -> list:
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("[")
    if start != -1:
        try:
            return json.loads(text[start:])
        except json.JSONDecodeError:
            pass
    return []
