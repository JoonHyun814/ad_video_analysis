"""비전 LLM 호출 디스패처. 공용 utils 호출기를 backend 이름으로 라우팅한다."""
from dataclasses import dataclass
from pathlib import Path

BACKENDS = ("gemini", "openai")


@dataclass(frozen=True)
class LlmConfig:
    backend: str
    model: str


def default_model(backend: str) -> str:
    """backend 별 utils 호출기의 기본 모델명을 반환한다."""
    if backend == "gemini":
        from utils.gemini_caller import DEFAULT_MODEL
    elif backend == "openai":
        from utils.openai_caller import DEFAULT_MODEL
    else:
        raise ValueError(f"지원하지 않는 backend: {backend} (가능: {BACKENDS})")
    return DEFAULT_MODEL


def call_vision(prompt: str, images: list[Path], backend: str, model: str) -> dict:
    """이미지 + 프롬프트로 비전 모델을 호출해 JSON dict 를 반환한다. 파싱 실패 시 error=parse_failed."""
    if backend == "gemini":
        from utils.gemini_caller import call_gemini_with_images
        return call_gemini_with_images(prompt, images, model=model, timeout=180)
    if backend == "openai":
        from utils.openai_caller import call_openai_with_images
        return call_openai_with_images(prompt, images, model=model, timeout=180)
    raise ValueError(f"지원하지 않는 backend: {backend} (가능: {BACKENDS})")
