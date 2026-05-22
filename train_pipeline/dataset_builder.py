"""pipeline 분석 결과를 Qwen VL 3 학습용 JSONL 데이터셋으로 변환한다."""

import json
from dataclasses import dataclass
from pathlib import Path

_MAX_CUT_FRAMES = 30

_SCENE_PROMPT = (
    "첨부 이미지를 분석하고 아래 JSON 형식으로만 응답해라. 마크다운 코드블록 없이 순수 JSON만 출력.\n\n"
    "OCR 참고 데이터 (오인식 포함 가능):\n{ocr_hint}\n\n"
    '{{"foreground": "전경 주요 피사체(인물·사물) 설명", "background": "배경 환경 설명",'
    ' "camera": "카메라 앵글·무브먼트 (예: close-up, wide-shot, pan, zoom, static, tracking)",'
    ' "mood": "장면 분위기·톤",'
    ' "text_overlay": "화면 텍스트 요소 묘사. 내용·종류·위치·폰트·색상. 없으면 없음"}}'
)

_CUT_PROMPT = (
    "첨부 이미지들은 {start_sec:.2f}~{end_sec:.2f}초 구간 광고 컷의 시간 순 프레임이다. "
    "분석하고 아래 JSON으로만 응답해라. 마크다운 없이 순수 JSON만 출력.\n\n"
    "프레임별 OCR 힌트 (오인식 포함 가능):\n{ocr_hints}\n\n"
    '{{"flow": "이 컷에서 일어나는 동작·변화를 시작→중간→끝 순으로 묘사",'
    ' "subjects": "등장 인물·사물",'
    ' "camera": "카메라 무브먼트 (static/pan/zoom/tilt/tracking 등)",'
    ' "text_flow": "텍스트 등장·변화·소멸 흐름. 없으면 없음",'
    ' "mood_shift": "분위기 변화. 없으면 없음"}}'
)

_SCENARIO_PROMPT_PREFIX = (
    "너는 광고 시나리오 전문가다. 아래 분석 데이터를 참고해 이 광고를 재제작할 수 있을 수준의 "
    "완전한 시나리오를 JSON으로 작성해라. 첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
    "규칙:\n"
    "1. cast 필드는 [등장 인물] 섹션에 제공된 캐릭터 목록을 그대로 사용한다.\n"
    "2. scenes[].beats: 각 컷 안의 시간 순 사건을 beat 단위로 나열한다.\n"
    "   - type=background: 배경·공간 변화 묘사\n"
    "   - type=camera: 카메라 앵글·무브먼트 묘사\n"
    "   - type=action: cast 필드에 캐릭터 ID, 동작 묘사\n"
    "   - type=dialogue: 대사·나레이션, cast 필드에 캐릭터 ID\n"
    "   - type=music: 음악·사운드 묘사\n"
    "   - type=text_overlay: 화면 텍스트. 없으면 beat 생략\n"
    "3. cast에 없는 캐릭터 ID를 beats에서 사용하지 않는다.\n\n"
)


@dataclass
class _Cut:
    index: int
    start_frame: int
    end_frame: int
    start_sec: float
    end_sec: float


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _build_frame_map(frames_dir: Path) -> dict[int, Path]:
    result = {}
    for p in frames_dir.glob("frame_*.jpg"):
        try:
            result[int(p.stem.replace("frame_", ""))] = p
        except ValueError:
            pass
    return result


def _get_cut_frames(frame_map: dict[int, Path], cut: _Cut) -> list[tuple[float, Path]]:
    span_frames = max(cut.end_frame - cut.start_frame, 1)
    span_sec = cut.end_sec - cut.start_sec
    return [
        (cut.start_sec + (idx - cut.start_frame) / span_frames * span_sec, p)
        for idx, p in sorted(frame_map.items())
        if cut.start_frame <= idx <= cut.end_frame
    ]


def _sample(frames: list, max_n: int) -> list:
    if len(frames) <= max_n:
        return frames
    step = len(frames) / max_n
    return [frames[int(i * step)] for i in range(max_n)]


def _cut_ocr(ocr_data: dict, cut: _Cut) -> str:
    texts: set[str] = set()
    for fname, words in ocr_data.items():
        try:
            idx = int(fname.replace("frame_", "").replace(".jpg", ""))
        except ValueError:
            continue
        if cut.start_frame <= idx <= cut.end_frame:
            texts.update(w for w in words if len(w.strip()) > 1)
    return ", ".join(f'"{t}"' for t in texts) if texts else "없음"


def _make_sample(image_paths: list[str], prompt: str, response: str) -> dict:
    content = [{"type": "image", "image": p} for p in image_paths]
    content.append({"type": "text", "text": prompt})
    return {
        "messages": [
            {"role": "user", "content": content},
            {"role": "assistant", "content": response},
        ]
    }


def _save_jsonl(samples: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(s, ensure_ascii=False) for s in samples),
        encoding="utf-8",
    )


# ── Per-step builders ──────────────────────────────────────────────────────────

def _scene_samples(video_dir: Path, cuts: list[_Cut], ocr_data: dict, scene_analysis: list[dict]) -> list[dict]:
    cut_map = {c.index: c for c in cuts}
    kf_dir = video_dir / "keyframes"
    samples = []
    for entry in scene_analysis:
        if entry.get("error"):
            continue
        kf_name = entry.get("keyframe", "")
        kf_path = kf_dir / kf_name if kf_name else None
        if not kf_path or not kf_path.exists():
            matches = list(kf_dir.glob(f"cut_{entry['cut_index']:03d}_*.jpg"))
            kf_path = matches[0] if matches else None
        if not kf_path or not kf_path.exists():
            continue
        cut = cut_map.get(entry["cut_index"])
        ocr_hint = _cut_ocr(ocr_data, cut) if cut else "없음"
        prompt = _SCENE_PROMPT.format(ocr_hint=ocr_hint)
        output = {k: v for k, v in entry.items() if k not in ("cut_index", "start_sec", "end_sec", "keyframe")}
        samples.append(_make_sample([str(kf_path)], prompt, json.dumps(output, ensure_ascii=False)))
    return samples


def _cut_samples(video_dir: Path, cuts: list[_Cut], ocr_data: dict, cut_analysis: list[dict]) -> list[dict]:
    cut_map = {c.index: c for c in cuts}
    frame_map = _build_frame_map(video_dir / "frames")
    samples = []
    for entry in cut_analysis:
        if entry.get("error"):
            continue
        cut = cut_map.get(entry["cut_index"])
        if not cut:
            continue
        sampled = _sample(_get_cut_frames(frame_map, cut), _MAX_CUT_FRAMES)
        if not sampled:
            continue
        hints_lines = []
        for t, p in sampled:
            words = ocr_data.get(p.name, [])
            ocr_str = ", ".join(f'"{x}"' for x in words) if words else "없음"
            hints_lines.append(f"{t:.2f}초: {ocr_str}")
        hints = "\n".join(hints_lines)
        prompt = _CUT_PROMPT.format(start_sec=cut.start_sec, end_sec=cut.end_sec, ocr_hints=hints)
        output = {k: v for k, v in entry.items() if k not in ("cut_index", "start_sec", "end_sec", "n_frames")}
        samples.append(_make_sample([str(p) for _, p in sampled], prompt, json.dumps(output, ensure_ascii=False)))
    return samples


def _scenario_samples(video_dir: Path, cuts: list[_Cut], cut_analysis: list[dict],
                      ocr_data: dict, stt: list[dict], scenario: dict) -> list[dict]:
    parts = []
    if stt:
        parts.append("[음성]\n" + " / ".join(f'{s["start_sec"]:.1f}s: "{s["text"]}"' for s in stt))
    cut_map = {c.index: c for c in cuts}
    if cut_analysis:
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
    context = "\n\n".join(parts)
    duration = max((c.end_sec for c in cuts), default=0.0)
    prompt = _SCENARIO_PROMPT_PREFIX + context + f"\n\n영상 길이: {round(duration, 1)}초"
    return [_make_sample([], prompt, json.dumps(scenario, ensure_ascii=False))]


# ── Main entry ─────────────────────────────────────────────────────────────────

def build_all(data_dir: Path, out_dir: Path) -> dict[str, int]:
    """data_dir 내 <video_id>/ 폴더를 순회해 4종 JSONL 데이터셋을 빌드한다."""
    buckets: dict[str, list[dict]] = {k: [] for k in ("scene_analysis", "cut_analysis", "scenario_analysis")}

    video_dirs = sorted(p for p in data_dir.iterdir() if p.is_dir() and p.name.isdigit())
    print(f"영상 폴더 {len(video_dirs)}개 발견")

    for vdir in video_dirs:
        cuts_raw = _load(vdir / "cuts.json")
        if not cuts_raw:
            continue
        cuts = [_Cut(**{k: c[k] for k in ("index", "start_frame", "end_frame", "start_sec", "end_sec")}) for c in cuts_raw]
        ocr_data = _load(vdir / "ocr.json") or {}
        scene = _load(vdir / "scene_analysis.json")
        cut_a = _load(vdir / "cut_analysis.json")
        stt = _load(vdir / "stt.json") or []
        scenario = _load(vdir / "scenario_analysis.json")

        vid = vdir.name
        if scene:
            s = _scene_samples(vdir, cuts, ocr_data, scene)
            buckets["scene_analysis"].extend(s)
            print(f"  [{vid}] scene: {len(s)}개")
        if cut_a:
            s = _cut_samples(vdir, cuts, ocr_data, cut_a)
            buckets["cut_analysis"].extend(s)
            print(f"  [{vid}] cut: {len(s)}개")
        if scenario and not scenario.get("error") and cut_a:
            s = _scenario_samples(vdir, cuts, cut_a, ocr_data, stt, scenario)
            buckets["scenario_analysis"].extend(s)
            print(f"  [{vid}] scenario: {len(s)}개")

    counts = {}
    for name, samples in buckets.items():
        if samples:
            path = out_dir / f"{name}.jsonl"
            _save_jsonl(samples, path)
            counts[name] = len(samples)
            print(f"\n{name}: {len(samples)}개  →  {path}")
    return counts
