import json
import re
import subprocess
import tempfile
from pathlib import Path

from pipeline.cuts import Cut
from pipeline.ocr import run_ocr

_PROMPT = """첨부 이미지를 분석하고 아래 JSON 형식으로만 응답해라. 마크다운 코드블록 없이 순수 JSON만 출력.

OCR 참고 데이터 (오인식 포함 가능):
{ocr_hint}

{{"foreground": "전경 주요 피사체(인물·사물) 설명", "background": "배경 환경 설명", "camera": "카메라 앵글·무브먼트 (예: close-up, wide-shot, pan, zoom, static, tracking)", "mood": "장면 분위기·톤", "text_overlay": "화면에 등장하는 텍스트 요소를 묘사. 텍스트 내용·종류(자막/슬로건/말풍선/로고 등)·위치(상/하/중앙/좌/우)·폰트 스타일(굵기·세리프 여부·크기감)·색상을 설명. 텍스트가 없으면 없음"}}"""


def analyze_keyframes_codex(
    cuts: list[Cut],
    keyframes_dir: Path,
    model: str | None = None,
) -> list[dict]:
    """각 컷의 keyframe에 OCR을 수행한 뒤 codex exec로 분석하고 결과 리스트를 반환한다.

    model: codex 모델명. None 이면 codex 기본값 사용.
    """
    keyframe_map = _build_keyframe_map(keyframes_dir)
    results = []

    for cut in cuts:
        image_path = keyframe_map.get(cut.index)
        if image_path is None:
            continue
        ocr_texts = run_ocr(image_path)
        ocr_hint = ", ".join(f'"{t}"' for t in ocr_texts) if ocr_texts else "없음"
        print(f"      [{cut.index}/{len(cuts)}] {image_path.name}  OCR: {ocr_hint}")
        analysis = _analyze_one(image_path, ocr_hint, model)
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


def _analyze_one(image_path: Path, ocr_hint: str, model: str | None) -> dict:
    prompt = _PROMPT.format(ocr_hint=ocr_hint)
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        out_file = Path(f.name)

    cmd = ["codex", "exec", "-i", str(image_path), "--dangerously-bypass-approvals-and-sandbox", "-o", str(out_file)]
    if model:
        cmd += ["-m", model]
    cmd.append(prompt)

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    return _parse_json(out_file.read_text(encoding="utf-8"))


def _parse_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {"error": "parse_failed", "raw": text}
