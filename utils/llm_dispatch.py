"""LLM 백엔드 통합 디스패처 — 파이프라인 모듈에서 공통으로 사용."""
from utils.gemini_caller import DEFAULT_MODEL as _GEMINI_DEFAULT
from utils.llm_caller import call_claude, call_codex


def call_llm(
    prompt: str,
    *,
    backend: str = "claude",
    gemini_model: str = "",
    codex_model: str | None = None,
    timeout: int = 300,
) -> dict:
    """backend에 따라 LLM을 호출하고 JSON dict를 반환한다."""
    if backend == "gemini":
        from utils.gemini_caller import call_gemini
        return call_gemini(prompt, model=gemini_model or _GEMINI_DEFAULT, timeout=timeout)
    if backend == "codex":
        return call_codex(prompt, model=codex_model, timeout=timeout)
    return call_claude(prompt, timeout=timeout)
