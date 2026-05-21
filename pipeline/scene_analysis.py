import json
import re
import subprocess
from pathlib import Path

from pipeline.cuts import Cut

_PROMPT = """파일 {image_path} 를 읽고 아래 JSON 형식으로만 응답해라. 마크다운 코드블록 없이 순수 JSON만 출력.

{{
  "foreground": "전경 주요 피사체(인물·사물) 설명",
  "background": "배경 환경 설명",
  "camera": "카메라 앵글·무브먼트 (예: close-up, wide-shot, pan, zoom, static, tracking)",
  "mood": "장면 분위기·톤",
  "text_overlay": ["화면에 보이는 텍스트 (없으면 빈 배열)"]
}}"""


def analyze_keyframes(cuts: list[Cut], keyframes_dir: Path, allowed_dir: Path) -> list[dict]:
    """각 컷의 keyframe을 claude -p로 분석하고 결과 리스트를 반환한다."""
    keyframe_map = _build_keyframe_map(keyframes_dir)
    results = []

    for cut in cuts:
        image_path = keyframe_map.get(cut.index)
        if image_path is None:
            continue
        print(f"      [{cut.index}/{len(cuts)}] {image_path.name}")
        analysis = _analyze_one(image_path, allowed_dir)
        results.append({
            "cut_index": cut.index,
            "start_sec": cut.start_sec,
            "end_sec": cut.end_sec,
            "keyframe": image_path.name,
            **analysis,
        })

    return results


def _build_keyframe_map(keyframes_dir: Path) -> dict[int, Path]:
    """cut_001_frame_xxxxx.jpg → {1: Path, ...}"""
    mapping: dict[int, Path] = {}
    for p in sorted(keyframes_dir.glob("cut_*.jpg")):
        try:
            mapping[int(p.name.split("_")[1])] = p
        except (IndexError, ValueError):
            pass
    return mapping


def _analyze_one(image_path: Path, allowed_dir: Path) -> dict:
    prompt = _PROMPT.format(image_path=image_path)
    result = subprocess.run(
        ["claude", "-p", prompt, "--add-dir", str(allowed_dir)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return _parse_json(result.stdout)


def _parse_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    try:
        data = json.loads(text)
        if data.get("text_overlay") is None:
            data["text_overlay"] = []
        return data
    except json.JSONDecodeError:
        return {"error": "parse_failed", "raw": text}
