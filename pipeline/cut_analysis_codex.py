import json
import re
import subprocess
import tempfile
from pathlib import Path

from pipeline.cut_analysis import _build_frame_map, _get_cut_frames, _sample
from pipeline.cuts import Cut

_MAX_FRAMES = 30

_PROMPT = """첨부 이미지들은 {start_sec:.2f}~{end_sec:.2f}초 구간 광고 컷의 시간 순 프레임이다. 분석하고 아래 JSON으로만 응답해라. 마크다운 없이 순수 JSON만 출력.

프레임별 OCR 힌트 (오인식 포함 가능):
{ocr_hints}

{{"flow": "이 컷에서 일어나는 동작·변화를 시작→중간→끝 순으로 묘사", "subjects": "등장 인물·사물", "camera": "카메라 무브먼트 (static/pan/zoom/tilt/tracking 등)", "text_flow": "텍스트 등장·변화·소멸 흐름. 없으면 없음", "mood_shift": "분위기 변화. 없으면 없음"}}"""


def analyze_cuts_codex(
    cuts: list[Cut],
    frames_dir: Path,
    ocr_data: dict[str, list[str]],
    model: str | None = None,
) -> list[dict]:
    """각 컷의 프레임 시퀀스를 codex exec로 분석해 시간 흐름을 묘사한다.

    model: codex 모델명. None 이면 codex 기본값 사용.
    """
    frame_map = _build_frame_map(frames_dir)
    results = []

    for cut in cuts:
        cut_frames = _get_cut_frames(frame_map, cut)
        sampled = _sample(cut_frames, _MAX_FRAMES)
        if not sampled:
            continue
        print(f"      [{cut.index}/{len(cuts)}] {cut.start_sec:.2f}~{cut.end_sec:.2f}s  {len(sampled)}프레임")
        analysis = _analyze_one(sampled, ocr_data, cut, model)
        results.append({
            "cut_index": cut.index,
            "start_sec": cut.start_sec,
            "end_sec": cut.end_sec,
            "n_frames": len(sampled),
            **analysis,
        })

    return results


def _analyze_one(
    frames: list[tuple[float, Path]],
    ocr_data: dict[str, list[str]],
    cut: Cut,
    model: str | None,
) -> dict:
    hints = []
    for t, p in frames:
        texts = ocr_data.get(p.name, [])
        ocr_str = ", ".join(f'"{x}"' for x in texts) if texts else "없음"
        hints.append(f"{t:.2f}초: {ocr_str}")

    prompt = _PROMPT.format(
        start_sec=cut.start_sec,
        end_sec=cut.end_sec,
        ocr_hints="\n".join(hints),
    )

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        out_file = Path(f.name)

    cmd = ["codex", "exec"]
    for _, p in frames:
        cmd += ["-i", str(p)]
    cmd += ["--dangerously-bypass-approvals-and-sandbox", "-o", str(out_file)]
    if model:
        cmd += ["-m", model]
    cmd.append(prompt)

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
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
