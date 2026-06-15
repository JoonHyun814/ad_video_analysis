"""컷 프레임 시퀀스를 Gemini Vision으로 분석한다."""
from pathlib import Path

from pipeline.cut_analysis import _build_frame_map, _get_cut_frames, _sample
from pipeline.cuts import Cut
from utils.gemini_caller import DEFAULT_MODEL, call_gemini_with_images

_MAX_FRAMES = 30

_PROMPT = """첨부 이미지들은 {start_sec:.2f}~{end_sec:.2f}초 구간 광고 컷의 시간 순 프레임이다.

이 구간 안에 SceneDetect가 놓친 장면 전환(배경·피사체·카메라 앵글이 갑자기 교체되는 지점)이 있으면
sub_cuts를 여러 개로 분할하라. 분할이 필요 없으면 sub_cuts에 원래 구간 하나만 넣는다.

프레임별 OCR 힌트 (오인식 포함 가능):
{ocr_hints}

마크다운 없이 순수 JSON만 출력.
{{
  "sub_cuts": [
    {{
      "start_sec": <float>,
      "end_sec": <float>,
      "flow": "동작·변화를 시작→중간→끝 순으로 묘사",
      "subjects": "등장 인물·사물",
      "cast": "각 인물의 외모(성별·나이대·헤어스타일·의상)·표정·역할. 인물이 없으면 없음",
      "camera": "static/pan/zoom/tilt/tracking 등",
      "text_flow": "텍스트 등장·변화·소멸 흐름. 없으면 없음",
      "mood_shift": "분위기 변화. 없으면 없음"
    }}
  ]
}}"""


def analyze_cuts_gemini(
    cuts: list[Cut],
    frames_dir: Path,
    ocr_data: dict[str, list[str]],
    model: str = DEFAULT_MODEL,
) -> list[dict]:
    """각 컷의 프레임 시퀀스를 Gemini Vision으로 분석하고, 모델이 추가 분할한 sub_cuts를 펼쳐 반환한다."""
    frame_map = _build_frame_map(frames_dir)
    flat: list[dict] = []

    for cut in cuts:
        cut_frames = _get_cut_frames(frame_map, cut)
        sampled = _sample(cut_frames, _MAX_FRAMES)
        if not sampled:
            continue
        print(f"      [{cut.index}/{len(cuts)}] {cut.start_sec:.2f}~{cut.end_sec:.2f}s  {len(sampled)}프레임")
        sub_cuts = _analyze_one(sampled, ocr_data, cut, model)
        n_sub = len(sub_cuts)
        if n_sub > 1:
            print(f"        → 모델 추가 분할: {n_sub}개 sub_cut")
        for sc in sub_cuts:
            flat.append({
                "cut_index": 0,
                "start_sec": sc.get("start_sec", cut.start_sec),
                "end_sec": sc.get("end_sec", cut.end_sec),
                "n_frames": len(sampled),
                "flow": sc.get("flow", ""),
                "subjects": sc.get("subjects", ""),
                "cast": sc.get("cast", "없음"),
                "camera": sc.get("camera", ""),
                "text_flow": sc.get("text_flow", "없음"),
                "mood_shift": sc.get("mood_shift", "없음"),
            })

    for i, entry in enumerate(flat, 1):
        entry["cut_index"] = i
    return flat


def _analyze_one(
    frames: list[tuple[float, Path]],
    ocr_data: dict[str, list[str]],
    cut: Cut,
    model: str,
) -> list[dict]:
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
    image_paths = [p for _, p in frames]
    raw = call_gemini_with_images(prompt, image_paths, model=model, timeout=180)

    sub_cuts = raw.get("sub_cuts")
    if isinstance(sub_cuts, list) and sub_cuts:
        return sub_cuts

    # 모델이 구형 포맷으로 응답하거나 sub_cuts가 없을 때 단일 sub_cut으로 래핑
    return [{
        "start_sec": cut.start_sec,
        "end_sec": cut.end_sec,
        **{k: v for k, v in raw.items() if k != "sub_cuts"},
    }]
