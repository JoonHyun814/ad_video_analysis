"""v5_m0_m3 LLM 어댑터 — 원본 app.services.llm_client.llm_chat 호출부를 이 프로젝트의
인프라로 교체한다. 텍스트 호출은 두 백엔드 중 선택 가능하다(set_backend, 기본 "cli"):

  - "cli" : utils.llm_caller.call_claude — 로컬 Claude Code CLI(`claude -p`) 서브프로세스 호출.
            API 키가 필요 없지만, 서브프로세스 기동·로그인 세션 오버헤드가 있어 --api 보다
            느릴 수 있다 — 그래서 기본 timeout 을 이 프로젝트 다른 CLI 헬퍼들의 기본값(300초)의
            2배(600초)로 늘렸다.
  - "api" : Anthropic 공식 SDK 로 Messages API 직접 호출(원본 소스 프로젝트의 backend='claude'와
            동일한 방식). env/api.env 의 ANTHROPIC_API_KEY 가 필요하다.

이미지 첨부 비전 호출(vision_json)은 백엔드 선택과 무관하게 항상 OpenAI Vision 을 쓴다 —
claude -p 도 Anthropic API 도 이 어댑터에서는 이미지 입력 경로를 만들지 않았다(현재
vision_json 호출부인 page_section_ocr 하나뿐이고, Anthropic API 로 옮기려면 별도 검증이
필요해 범위를 좁혔다).
"""
from __future__ import annotations

import contextvars
import logging
import tempfile
from pathlib import Path

from utils.env_loader import load_env
from utils.json_utils import parse_json
from utils.llm_caller import call_claude
from utils.openai_caller import call_openai_with_images

logger = logging.getLogger(__name__)

_VALID_BACKENDS = ("cli", "api")
_backend: contextvars.ContextVar[str] = contextvars.ContextVar("v5_m0_m3_llm_backend", default="cli")

_CLI_DEFAULT_TIMEOUT = 300
_CLI_TIMEOUT_MULTIPLIER = 2  # cli(서브프로세스) 백엔드는 api 대비 느릴 수 있어 기본 timeout 2배

_API_DEFAULT_MODEL = "claude-sonnet-5"
_API_MAX_TOKENS = 8000
_JSON_FORCE_INSTRUCTION = (
    "\n\n[OUTPUT FORMAT — STRICT]\n"
    "Reply with ONLY a single valid JSON object.\n"
    "No markdown code fences, no preamble, no trailing text, no explanations.\n"
    "Start with { and end with }."
)

_anthropic_client = None


def set_backend(backend: str) -> None:
    """텍스트 LLM 호출 백엔드를 지정한다 — "cli"(claude -p, 기본) | "api"(Anthropic API 직접).

    CLI 진입점(cli.py/cli_m4_m9.py)이 --llm_backend 인자를 받아 실행 시작 시 1회 호출한다.
    """
    b = (backend or "cli").strip().lower()
    if b not in _VALID_BACKENDS:
        raise ValueError(f"unknown llm backend: {backend!r} (valid: {_VALID_BACKENDS})")
    _backend.set(b)


def get_backend() -> str:
    return _backend.get()


def _anthropic_api_key() -> str:
    import os
    return os.environ.get("ANTHROPIC_API_KEY") or (load_env("env/api.env").get("ANTHROPIC_API_KEY") or "")


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        api_key = _anthropic_api_key()
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY가 환경변수나 env/api.env에서 발견되지 않았습니다.")
        _anthropic_client = anthropic.Anthropic(api_key=api_key)
    return _anthropic_client


def _chat_json_api(system: str, user: str) -> dict:
    """Anthropic Messages API 직접 호출. json_mode 는 response_format 이 없어 프롬프트 강제 + 파싱 복구로 대신한다."""
    client = _get_anthropic_client()
    msg = client.messages.create(
        model=_API_DEFAULT_MODEL,
        max_tokens=_API_MAX_TOKENS,
        system=system + _JSON_FORCE_INSTRUCTION,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")
    return parse_json(text)


def _chat_json_cli(system: str, user: str, *, timeout: int) -> dict:
    prompt = f"{system}\n\n---\n\n{user}\n\n위 입력으로 지시를 수행하고, JSON 객체 하나로만 응답하세요."
    return call_claude(prompt, timeout=timeout * _CLI_TIMEOUT_MULTIPLIER)


def chat_json(system: str, user: str, *, timeout: int = _CLI_DEFAULT_TIMEOUT) -> dict:
    """system+user 프롬프트를 현재 백엔드(get_backend())로 실행하고 JSON dict 를 반환한다.

    timeout 은 "cli" 백엔드에만 적용되며(위 docstring 참고), 실제로는 이 값의
    _CLI_TIMEOUT_MULTIPLIER(2)배가 call_claude 에 전달된다. "api" 백엔드는 SDK 기본
    타임아웃을 쓴다. 실패해도 예외를 던지지 않고 {"error": "parse_failed", ...} 를 반환한다
    (utils.json_utils.parse_json 계약 — 호출부가 빈 결과로 graceful 처리).
    """
    backend = get_backend()
    if backend == "api":
        try:
            return _chat_json_api(system, user)
        except Exception as e:
            logger.warning(f"[llm_adapter] api backend fail, no fallback: {type(e).__name__}: {e}")
            return {"error": "parse_failed", "raw": str(e)}
    return _chat_json_cli(system, user, timeout=timeout)


def vision_json(prompt: str, images: list[tuple[bytes, str]], *, model: str | None = None) -> dict:
    """이미지 여러 장 + 텍스트 지시를 OpenAI Vision 으로 분석해 JSON dict 를 반환한다.

    images: [(raw_bytes, file_ext), ...]. call_openai_with_images 가 로컬 파일 경로만
    받으므로 임시 파일에 내려쓴 뒤 호출한다. 텍스트 백엔드 선택(set_backend)과 무관하게
    항상 OpenAI Vision 을 쓴다(모듈 docstring 참고).
    """
    if not images:
        return {}
    with tempfile.TemporaryDirectory(prefix="v5_vision_") as tmpdir:
        paths: list[Path] = []
        for i, (raw, ext) in enumerate(images):
            p = Path(tmpdir) / f"img{i}.{ext or 'jpg'}"
            p.write_bytes(raw)
            paths.append(p)
        kwargs = {"model": model} if model else {}
        return call_openai_with_images(prompt, paths, **kwargs)
