"""후보 태그를 태그 1개씩 yes/no 로 재검증한다. 생성 단계의 근거는 보여주지 않는다."""
from pikk_tagging.frame_select import FrameList
from pikk_tagging.llm import LlmConfig, call_vision
from pikk_tagging.prompts import build_verify_prompt
from pikk_tagging.schema import clean_frames
from pikk_tagging.vocab import Technique
from utils.io_checks import is_parse_failed


def verify_tag(tech: Technique, frames: FrameList, span: tuple[float, float], llm: LlmConfig) -> dict:
    """{'present': bool|None, 'frames': [...], 'reason': str}. 호출·파싱 실패는 present=None 이다."""
    prompt = build_verify_prompt(tech, frames, span)
    try:
        raw = call_vision(prompt, [p for _, p in frames], llm.backend, llm.model)
    except Exception as e:  # 네트워크·쿼터 오류가 컷 전체 태깅을 죽이지 않도록 기록만 한다
        return {"present": None, "frames": [], "reason": f"call_error: {e}"}
    if not isinstance(raw, dict) or is_parse_failed(raw):
        return {"present": None, "frames": [], "reason": "parse_failed"}
    ev_frames = clean_frames(raw.get("frames"), len(frames))
    present = raw.get("present") is True and bool(ev_frames)
    return {"present": present, "frames": ev_frames, "reason": str(raw.get("reason", "")).strip()}
