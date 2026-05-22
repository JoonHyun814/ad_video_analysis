import json
import re
import subprocess
from pathlib import Path

import cv2

from pipeline.cuts import Cut

_SCHEMA = '[{"id": "캐릭터1", "description": "외모·인상·역할을 구체적으로 묘사"}]'


def analyze_cast(
    cuts: list[Cut],
    frames_dir: Path,
    face_detection: dict[str, list[dict]],
    cut_analysis: list[dict],
    out_dir: Path,
) -> list[dict]:
    """얼굴 크롭 + cut_analysis를 참고해 등장 인물 cast 리스트를 반환한다."""
    face_crops = _save_face_crops(frames_dir, cuts, face_detection, out_dir)
    if not face_crops:
        return []
    context = _build_context(cut_analysis, face_crops)
    return _call_claude(context, out_dir)


# ── Face crop ─────────────────────────────────────────────────────────────────

def _save_face_crops(
    frames_dir: Path,
    cuts: list[Cut],
    face_detection: dict[str, list[dict]],
    out_dir: Path,
) -> list[tuple[Path, str]]:
    """각 컷에서 가장 큰 얼굴을 패딩 포함해 crop 저장하고 (path, label) 리스트를 반환한다."""
    crops_dir = out_dir / "face_crops"
    crops_dir.mkdir(parents=True, exist_ok=True)
    frame_map = {p.name: p for p in frames_dir.glob("frame_*.jpg")}

    result = []
    for cut in cuts:
        best: tuple[float, str, list[int]] | None = None
        for fname, faces in face_detection.items():
            try:
                idx = int(fname.replace("frame_", "").replace(".jpg", ""))
            except ValueError:
                continue
            if not (cut.start_frame <= idx <= cut.end_frame):
                continue
            for face in faces:
                if best is None or face["area_ratio"] > best[0]:
                    best = (face["area_ratio"], fname, face["bbox"])

        if best is None or best[0] < 0.01 or best[1] not in frame_map:
            continue

        _, fname, (x, y, w, h) = best
        img = cv2.imread(str(frame_map[fname]))
        if img is None:
            continue

        pad = int(max(w, h) * 0.25)
        ih, iw = img.shape[:2]
        crop = img[max(0, y - pad): min(ih, y + h + pad),
                   max(0, x - pad): min(iw, x + w + pad)]
        crop_path = crops_dir / f"face_cut{cut.index:02d}.jpg"
        cv2.imwrite(str(crop_path), crop)
        result.append((crop_path, f"컷{cut.index} ({cut.start_sec:.1f}~{cut.end_sec:.1f}s)"))

    return result


# ── Context building ───────────────────────────────────────────────────────────

def _build_context(cut_analysis: list[dict], face_crops: list[tuple[Path, str]]) -> str:
    parts = []

    if cut_analysis:
        lines = []
        for c in cut_analysis:
            if c.get("error"):
                continue
            subj = c.get("subjects", "")
            lines.append(f"컷{c['cut_index']} {c['start_sec']:.1f}~{c['end_sec']:.1f}s: {subj}")
        if lines:
            parts.append("[컷별 등장 인물 힌트]\n" + "\n".join(lines))

    refs = "\n".join(f"파일 {p}  ({label})" for p, label in face_crops)
    parts.append(f"[얼굴 이미지 — 아래 파일을 읽어 인물을 파악한다]\n{refs}")

    return "\n\n".join(parts)


# ── Claude call ────────────────────────────────────────────────────────────────

def _call_claude(context: str, out_dir: Path) -> list[dict]:
    prompt = (
        "너는 광고 캐스팅 분석 전문가다. 첨부된 얼굴 이미지와 컷별 등장 인물 힌트를 참고해 "
        "이 광고에 등장하는 모든 인물을 파악하고 cast 리스트를 JSON 배열로 작성해라. "
        "첫 글자가 반드시 '['여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
        "규칙:\n"
        "1. 동일 인물이 여러 컷에 등장하면 하나의 캐릭터 ID로 통합한다.\n"
        "2. 각 인물에 '캐릭터1', '캐릭터2' 등 순번 ID를 부여한다.\n"
        "3. description에는 외모·인상·역할을 구체적으로 묘사한다.\n\n"
        f"{context}\n\n"
        f"{_SCHEMA}"
    )
    result = subprocess.run(
        ["claude", "-p", prompt, "--add-dir", str(out_dir)],
        capture_output=True, text=True, timeout=300,
    )
    return _parse_json(result.stdout)


def _parse_json(text: str) -> list:
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
