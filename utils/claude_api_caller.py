"""Anthropic Claude API 호출 유틸리티 — Gemini/OpenAI caller와 동일한 인터페이스.

`llm_caller.call_claude`(claude -p CLI)와 달리 Anthropic SDK로 Messages API를 직접 호출한다.
로그인된 `claude` CLI 세션이 없는 서버·배치 프로세스에서 API 키만으로 돌리고 싶을 때 쓴다
(generation/v5_m0_m3/llm_adapter.py의 `--llm_backend api`와 동일한 방식, 별도 재구현).
"""
import os
import time
from pathlib import Path

from utils.json_utils import parse_json

DEFAULT_MODEL = "claude-sonnet-5"
_MAX_OUTPUT_TOKENS = 24000  # 이 한도 이상은 Anthropic SDK가 비-스트리밍 호출을 거부하고 스트리밍을 요구한다
_RETRY_DELAYS = (30, 60, 120)
_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY") or _load_api_key()
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY가 환경변수나 env/api.env에서 발견되지 않았습니다.")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def _load_api_key() -> str:
    """env/api.env에서 ANTHROPIC_API_KEY를 읽는다."""
    env_path = Path(__file__).parent.parent / "env" / "api.env"
    if not env_path.exists():
        return ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("ANTHROPIC_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _text_of(msg) -> str:
    return "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")


def _generate(model: str, prompt: str, timeout: int) -> str:
    """재시도 로직 포함 Anthropic API 호출(스트리밍). 원시 텍스트를 반환한다."""
    client = _get_client()
    text = ""
    for attempt, delay in enumerate((*_RETRY_DELAYS, None), start=1):
        try:
            with client.messages.stream(
                # temperature 미지정 — claude-sonnet-5 계열은 명시적 temperature 를
                # "deprecated" 400 에러로 거부한다(generation/v5_m0_m3/llm_adapter.py 도 동일).
                model=model,
                max_tokens=_MAX_OUTPUT_TOKENS,
                messages=[{"role": "user", "content": prompt}],
                timeout=timeout,
            ) as stream:
                msg = stream.get_final_message()
            return _text_of(msg)
        except Exception as e:
            text = str(e)
            is_overloaded = "529" in text or "overloaded" in text.lower()
            if not is_overloaded:
                raise
        if delay is None:
            break
        print(f"      Claude API overloaded, retrying in {delay}s ({attempt}/{len(_RETRY_DELAYS)})...")
        time.sleep(delay)
    return text


def call_claude_api(prompt: str, model: str = DEFAULT_MODEL, timeout: int = 300) -> dict:
    """Anthropic API로 텍스트 프롬프트를 실행하고 JSON 결과를 반환한다."""
    return parse_json(_generate(model, prompt, timeout))
