"""Qwen2.5-VL 로컬 모델을 이용한 cut 분석."""
from pathlib import Path

from pipeline import qwen_client
from pipeline.cut_analysis import _build_frame_map, _get_cut_frames, _sample
from pipeline.cuts import Cut

_MAX_FRAMES = 30

_PROMPT = (
    "첨부 이미지들은 {start_sec:.2f}~{end_sec:.2f}초 구간 광고 컷의 시간 순 프레임이다. "
    "분석하고 아래 JSON으로만 응답해라. 마크다운 없이 순수 JSON만 출력.\n\n"
    "프레임별 OCR 힌트 (오인식 포함 가능):\n{ocr_hints}\n\n"
    '{{"flow": "이 컷에서 일어나는 동작·변화를 시작→중간→끝 순으로 묘사",'
    ' "subjects": "등장 인물·사물",'
    ' "cast": "이 컷에 등장하는 각 인물의 외모(성별·나이대·헤어스타일·의상)·표정·역할을 구체적으로 묘사. 인물이 없으면 없음",'
    ' "camera": "카메라 무브먼트 (static/pan/zoom/tilt/tracking 등)",'
    ' "text_flow": "텍스트 등장·변화·소멸 흐름. 없으면 없음",'
    ' "mood_shift": "분위기 변화. 없으면 없음"}}'
)


def analyze_cuts_qwen(
    cuts: list[Cut],
    frames_dir: Path,
    ocr_data: dict[str, list[str]],
) -> list[dict]:
    """각 컷의 프레임 시퀀스를 Qwen 로컬 모델로 분석한다."""
    frame_map = _build_frame_map(frames_dir)
    results = []

    for cut in cuts:
        cut_frames = _get_cut_frames(frame_map, cut)
        sampled = _sample(cut_frames, _MAX_FRAMES)
        if not sampled:
            continue

        print(f"      [{cut.index}/{len(cuts)}] {cut.start_sec:.2f}~{cut.end_sec:.2f}s  {len(sampled)}프레임")

        hints = []
        for t, p in sampled:
            texts = ocr_data.get(p.name, [])
            ocr_str = ", ".join(f'"{x}"' for x in texts) if texts else "없음"
            hints.append(f"{t:.2f}초: {ocr_str}")

        prompt = _PROMPT.format(
            start_sec=cut.start_sec,
            end_sec=cut.end_sec,
            ocr_hints="\n".join(hints),
        )
        raw = qwen_client.infer([p for _, p in sampled], prompt)
        analysis = qwen_client.parse_json(raw)

        results.append({
            "cut_index": cut.index,
            "start_sec": cut.start_sec,
            "end_sec": cut.end_sec,
            "n_frames": len(sampled),
            **analysis,
        })

    return results
