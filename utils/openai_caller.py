"""OpenAI API 호출 유틸리티 — Gemini caller와 동일한 인터페이스."""
import base64
import os
import time
from pathlib import Path

from openai import OpenAI, RateLimitError

from utils.json_utils import parse_json

DEFAULT_MODEL = "gpt-4o-mini"
_TEMPERATURE = 0.0
_MAX_OUTPUT_TOKENS = 16384
_RETRY_DELAYS = (30, 60, 120)
_client: OpenAI | None = None
_token_usage: dict[str, int] = {"input": 0, "output": 0, "thinking": 0}


def get_token_usage() -> dict[str, int]:
    """누적 토큰 사용량을 반환한다."""
    return dict(_token_usage)


def reset_token_usage() -> None:
    """누적 토큰 카운터를 초기화한다."""
    _token_usage.update({"input": 0, "output": 0, "thinking": 0})


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY") or _load_api_key()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY가 환경변수나 env/api.env에서 발견되지 않았습니다.")
        _client = OpenAI(api_key=api_key)
    return _client


def _load_api_key() -> str:
    """env/api.env에서 OPENAI_API_KEY를 읽는다."""
    env_path = Path(__file__).parent.parent / "env" / "api.env"
    if not env_path.exists():
        return ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("OPENAI_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _chat_with_retry(model: str, messages: list) -> str:
    client = _get_client()
    text = ""
    for attempt, delay in enumerate((*_RETRY_DELAYS, None), start=1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=_TEMPERATURE,
                max_tokens=_MAX_OUTPUT_TOKENS,
                response_format={"type": "json_object"},
            )
            text = response.choices[0].message.content or ""
            _accumulate_tokens(response)
            return text
        except RateLimitError as e:
            text = str(e)
            if delay is None:
                raise
            print(f"      OpenAI rate limit, retrying in {delay}s ({attempt}/{len(_RETRY_DELAYS)})...")
            time.sleep(delay)
    return text


def call_openai(prompt: str, model: str = DEFAULT_MODEL, timeout: int = 300) -> dict:
    """OpenAI API로 텍스트 프롬프트를 실행하고 JSON 결과를 반환한다."""
    messages = [{"role": "user", "content": prompt}]
    return parse_json(_chat_with_retry(model, messages))


def call_openai_with_images(
    prompt: str,
    image_paths: list[Path],
    model: str = DEFAULT_MODEL,
    timeout: int = 300,
) -> dict:
    """이미지 리스트와 텍스트를 OpenAI Vision API로 분석하고 JSON 결과를 반환한다."""
    content: list = []
    for p in image_paths:
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })
    content.append({"type": "text", "text": prompt})
    messages = [{"role": "user", "content": content}]
    return parse_json(_chat_with_retry(model, messages))


def _accumulate_tokens(response) -> None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    _token_usage["input"] += getattr(usage, "prompt_tokens", 0) or 0
    _token_usage["output"] += getattr(usage, "completion_tokens", 0) or 0
    # OpenAI에는 thinking token 개념이 없어 형태 유지를 위해 0으로 둔다.
