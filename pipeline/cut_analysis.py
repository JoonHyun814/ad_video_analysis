import json
from utils.json_utils import parse_json as _parse_json
import subprocess
from pathlib import Path

from pipeline.cuts import Cut

_MAX_FRAMES = 30

_PROMPT = """{start_sec:.2f}~{end_sec:.2f}초 구간의 광고 컷을 시간 순으로 분석하라. 마크다운 없이 순수 JSON만 출력.

아래 {n}개 프레임을 순서대로 읽어라:
{frame_lines}

{{"flow": "이 컷에서 일어나는 동작·변화를 시작→중간→끝 순으로 묘사", "subjects": "등장 인물·사물", "cast": "이 컷에 등장하는 각 인물의 외모(성별·나이대·헤어스타일·의상)·표정·역할을 구체적으로 묘사. 인물이 없으면 없음", "camera": "카메라 무브먼트 (static/pan/zoom/tilt/tracking 등)", "text_flow": "텍스트 등장·변화·소멸 흐름. 없으면 없음", "mood_shift": "분위기 변화. 없으면 없음"}}"""


def analyze_cuts(
    cuts: list[Cut],
    frames_dir: Path,
    ocr_data: dict[str, list[str]],
    allowed_dir: Path,
) -> list[dict]:
    """각 컷의 fps=2 프레임 시퀀스를 claude로 분석해 시간 흐름을 묘사한다."""
    frame_map = _build_frame_map(frames_dir)
    results = []

    for cut in cuts:
        cut_frames = _get_cut_frames(frame_map, cut)
        sampled = _sample(cut_frames, _MAX_FRAMES)
        if not sampled:
            continue
        print(f"      [{cut.index}/{len(cuts)}] {cut.start_sec:.2f}~{cut.end_sec:.2f}s  {len(sampled)}프레임")
        analysis = _analyze_one(sampled, ocr_data, cut, allowed_dir)
        results.append({
            "cut_index": cut.index,
            "start_sec": cut.start_sec,
            "end_sec": cut.end_sec,
            "n_frames": len(sampled),
            **analysis,
        })

    return results


def _build_frame_map(frames_dir: Path) -> dict[int, Path]:
    mapping: dict[int, Path] = {}
    for p in frames_dir.glob("frame_*.jpg"):
        try:
            mapping[int(p.stem.replace("frame_", ""))] = p
        except ValueError:
            pass
    return mapping


def _get_cut_frames(
    frame_map: dict[int, Path], cut: Cut,
) -> list[tuple[float, Path]]:
    """컷 범위에 속하는 프레임을 (time_sec, path) 리스트로 반환한다."""
    span_frames = max(cut.end_frame - cut.start_frame, 1)
    span_sec = cut.end_sec - cut.start_sec
    frames = []
    for idx, p in frame_map.items():
        if cut.start_frame <= idx <= cut.end_frame:
            t = cut.start_sec + (idx - cut.start_frame) / span_frames * span_sec
            frames.append((round(t, 2), p))
    return sorted(frames, key=lambda x: x[0])


def _sample(frames: list, max_n: int) -> list:
    if len(frames) <= max_n:
        return frames
    step = len(frames) / max_n
    return [frames[int(i * step)] for i in range(max_n)]


def _analyze_one(
    frames: list[tuple[float, Path]],
    ocr_data: dict[str, list[str]],
    cut: Cut,
    allowed_dir: Path,
) -> dict:
    lines = []
    for i, (t, p) in enumerate(frames, 1):
        texts = ocr_data.get(p.name, [])
        ocr_str = ", ".join(f'"{x}"' for x in texts) if texts else "없음"
        lines.append(f"[{i}/{len(frames)}] {t:.2f}초  파일: {p}  OCR: {ocr_str}")

    prompt = _PROMPT.format(
        start_sec=cut.start_sec,
        end_sec=cut.end_sec,
        n=len(frames),
        frame_lines="\n".join(lines),
    )
    result = subprocess.run(
        ["claude", "-p", prompt, "--add-dir", str(allowed_dir)],
        capture_output=True,
        text=True,
        timeout=180,
    )
    return _parse_json(result.stdout)

