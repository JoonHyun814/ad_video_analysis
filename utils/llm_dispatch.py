"""LLM 백엔드 통합 디스패처 — 파이프라인 모듈에서 공통으로 사용."""
from utils.gemini_caller import DEFAULT_MODEL as _GEMINI_DEFAULT
from utils.llm_caller import call_claude, call_codex


def call_llm(
    prompt: str,
    *,
    backend: str = "claude",
    gemini_model: str = "",
    codex_model: str | None = None,
    claude_api_model: str = "",
    qwen_model_path: str | None = None,
    timeout: int = 300,
) -> dict:
    """backend에 따라 LLM을 호출하고 JSON dict를 반환한다.

    backend="claude"는 `claude -p` CLI(로그인 세션 필요, API 키 불필요), backend="claude_api"는
    Anthropic API 직접 호출(ANTHROPIC_API_KEY 필요, CLI 세션 불필요) — 둘은 별도 백엔드다.
    backend="qwen_vl"은 로컬 Qwen2.5-VL 모델 추론(텍스트 전용, 이미지 없음).
    이미지 입력이 필요하면 utils.qwen_vl_caller.QwenVLModel 을 직접 사용한다.
    """
    if backend == "gemini":
        from utils.gemini_caller import call_gemini
        return call_gemini(prompt, model=gemini_model or _GEMINI_DEFAULT, timeout=timeout)
    if backend == "codex":
        return call_codex(prompt, model=codex_model, timeout=timeout)
    if backend == "claude_api":
        from utils.claude_api_caller import DEFAULT_MODEL as _CLAUDE_API_DEFAULT
        from utils.claude_api_caller import call_claude_api
        return call_claude_api(prompt, model=claude_api_model or _CLAUDE_API_DEFAULT, timeout=timeout)
    if backend == "qwen_vl":
        from utils.qwen_vl_caller import call_qwen_vl
        return call_qwen_vl(prompt, image_paths=None, model_path=qwen_model_path)
    return call_claude(prompt, timeout=timeout)
