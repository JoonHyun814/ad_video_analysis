"""Google Gemini API 호출 유틸리티."""
import os
import time
from pathlib import Path

from google import genai
from google.genai import types

from utils.json_utils import parse_json

DEFAULT_MODEL = "models/gemini-2.5-flash-lite"
_TEMPERATURE = 0.0
_MAX_OUTPUT_TOKENS = 16384
_RETRY_DELAYS = (30, 60, 120)
_client: genai.Client | None = None
_token_usage: dict[str, int] = {"input": 0, "output": 0, "thinking": 0}


def get_token_usage() -> dict[str, int]:
    """누적 토큰 사용량을 반환한다."""
    return dict(_token_usage)


def reset_token_usage() -> None:
    """누적 토큰 카운터를 초기화한다."""
    _token_usage.update({"input": 0, "output": 0, "thinking": 0})


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY") or _load_api_key()
        _client = genai.Client(api_key=api_key)
    return _client


def _load_api_key() -> str:
    """env/api.env 에서 GEMINI_API_KEY를 읽는다."""
    env_path = Path(__file__).parent.parent / "env" / "api.env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("GEMINI_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                if key:
                    return key
    raise RuntimeError("GEMINI_API_KEY was not found in the environment or env/api.env")


def _make_config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        temperature=_TEMPERATURE,
        max_output_tokens=_MAX_OUTPUT_TOKENS,
        response_mime_type="application/json",
    )


def _generate(model: str, contents) -> str:
    """재시도 로직 포함 Gemini API 호출. 원시 텍스트를 반환한다."""
    client = _get_client()
    config = _make_config()
    text = ""
    for attempt, delay in enumerate((*_RETRY_DELAYS, None), start=1):
        try:
            response = client.models.generate_content(
                model=model, contents=contents, config=config
            )
            text = response.text or ""
            _accumulate_tokens(response)
            return text
        except Exception as e:
            text = str(e)
            is_quota = "429" in text or "quota" in text.lower() or "resource_exhausted" in text.lower()
            if not is_quota:
                raise
        if delay is None:
            break
        print(f"      Gemini quota/load limit, retrying in {delay}s ({attempt}/{len(_RETRY_DELAYS)})...")
        time.sleep(delay)
    return text


def call_gemini(prompt: str, model: str = DEFAULT_MODEL, timeout: int = 300) -> dict:
    """Gemini API로 텍스트 프롬프트를 실행하고 JSON 결과를 반환한다."""
    return parse_json(_generate(model, prompt))


def call_gemini_with_images(
    prompt: str,
    image_paths: list[Path],
    model: str = DEFAULT_MODEL,
    timeout: int = 300,
) -> dict:
    """이미지 리스트와 텍스트를 Gemini Vision API로 분석하고 JSON 결과를 반환한다."""
    return parse_json(_generate_with_images(prompt, image_paths, model))


def call_gemini_with_images_raw(
    prompt: str,
    image_paths: list[Path],
    model: str = DEFAULT_MODEL,
    timeout: int = 300,
) -> str:
    """이미지 리스트와 텍스트를 Gemini Vision API로 분석하고 원시 텍스트를 반환한다."""
    return _generate_with_images(prompt, image_paths, model)


def _accumulate_tokens(response) -> None:
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return
    _token_usage["input"] += getattr(usage, "prompt_token_count", 0) or 0
    _token_usage["output"] += getattr(usage, "candidates_token_count", 0) or 0
    _token_usage["thinking"] += getattr(usage, "thoughts_token_count", 0) or 0


def _generate_with_images(prompt: str, image_paths: list[Path], model: str) -> str:
    parts: list = [
        types.Part.from_bytes(data=p.read_bytes(), mime_type="image/jpeg")
        for p in image_paths
    ]
    parts.append(types.Part.from_text(text=prompt))
    return _generate(model, parts)
