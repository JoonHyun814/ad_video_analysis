"""Qwen2.5-VL 로컬 모델을 이용한 scene(keyframe) 분석."""
from pathlib import Path

from pipeline import qwen_client
from pipeline.cuts import Cut
from pipeline.ocr import run_ocr
from pipeline.scene_analysis_codex import _build_keyframe_map

_PROMPT = (
    "첨부 이미지를 분석하고 아래 JSON 형식으로만 응답해라. 마크다운 코드블록 없이 순수 JSON만 출력.\n\n"
    "OCR 참고 데이터 (오인식 포함 가능):\n{ocr_hint}\n\n"
    '{{"foreground": "전경 주요 피사체(인물·사물) 설명", "background": "배경 환경 설명",'
    ' "camera": "카메라 앵글·무브먼트 (예: close-up, wide-shot, pan, zoom, static, tracking)",'
    ' "mood": "장면 분위기·톤",'
    ' "text_overlay": "화면 텍스트 요소 묘사. 내용·종류·위치·폰트·색상. 없으면 없음"}}'
)


def analyze_keyframes_qwen(cuts: list[Cut], keyframes_dir: Path) -> list[dict]:
    """각 컷의 keyframe 을 Qwen 로컬 모델로 분석한다."""
    keyframe_map = _build_keyframe_map(keyframes_dir)
    results = []

    for cut in cuts:
        image_path = keyframe_map.get(cut.index)
        if image_path is None:
            continue
        ocr_texts = run_ocr(image_path)
        ocr_hint = ", ".join(f'"{t}"' for t in ocr_texts) if ocr_texts else "없음"
        print(f"      [{cut.index}/{len(cuts)}] {image_path.name}  OCR: {ocr_hint}")

        prompt = _PROMPT.format(ocr_hint=ocr_hint)
        raw = qwen_client.infer([image_path], prompt)
        analysis = qwen_client.parse_json(raw)
        status = "FAIL" if analysis.get("error") else "ok"
        print(f"      [{cut.index}/{len(cuts)}] parse: {status}")

        results.append({
            "cut_index": cut.index,
            "start_sec": cut.start_sec,
            "end_sec": cut.end_sec,
            "keyframe": image_path.name,
            **analysis,
        })

    return results
