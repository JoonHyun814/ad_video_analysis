"""Qwen2.5-VL 로컬 모델을 이용한 시나리오 분석 (텍스트 전용)."""
from pipeline import qwen_client
from pipeline.cuts import Cut
from pipeline.scenario_analysis import _SCHEMA, _build_context

_PROMPT_PREFIX = (
    "너는 광고 시나리오 전문가다. 아래 분석 데이터를 참고해 이 광고를 재제작할 수 있을 수준의 "
    "완전한 시나리오를 JSON으로 작성해라. 첫 글자가 반드시 '{'여야 한다. 마크다운·설명문 없이 순수 JSON만 출력.\n\n"
    "규칙:\n"
    "1. cast: 컷별 흐름의 '인물' 설명을 종합해 전체 등장 인물 목록을 직접 구성한다. "
    "동일 인물은 하나의 캐릭터 ID('캐릭터1', '캐릭터2' 등)로 통합한다.\n"
    "2. scenes[].beats: 각 컷 안의 시간 순 사건을 beat 단위로 나열한다.\n"
    "   - type=background: 배경·공간 변화 묘사\n"
    "   - type=camera: 카메라 앵글·무브먼트 묘사\n"
    "   - type=action: cast에 정의된 캐릭터 ID를 cast 필드에 적고 동작 묘사 (여럿이면 '캐릭터1,캐릭터2')\n"
    "   - type=dialogue: 대사·나레이션, cast 필드에 캐릭터 ID\n"
    "   - type=music: 음악·사운드 묘사\n"
    "   - type=text_overlay: 화면에 표시된 텍스트. 없으면 beat 자체를 생략\n"
    "3. cast에 없는 캐릭터 ID를 beats에서 사용하지 않는다.\n\n"
)


def analyze_scenario_qwen(
    cuts: list[Cut],
    frames_dir,
    cut_analysis: list[dict],
    ocr_data: dict[str, list[str]],
    stt_segments: list[dict],
    audio_data: dict | None = None,
) -> dict:
    """컷분석·OCR·STT·오디오 데이터를 Qwen 로컬 모델로 종합해 광고 시나리오를 생성한다."""
    duration = max((c.end_sec for c in cuts), default=0.0)
    context = _build_context(cuts, cut_analysis, ocr_data, stt_segments, audio_data)
    prompt = (
        _PROMPT_PREFIX
        + f"영상 길이: {round(duration, 1)}초\n\n"
        + context
        + f"\n\n{_SCHEMA}"
    )
    raw = qwen_client.infer([], prompt, max_new_tokens=8192)
    return qwen_client.parse_json(raw)
