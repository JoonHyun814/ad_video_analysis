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

[신규] set_retrieval(True) — evaluation/creative 크리에이티브 벡터 DB를 MCP 서버로 노출한
`creative-retrieval`(저장소 루트 `.mcp.json`, evaluation/creative/mcp_server.py)의 도구를
텍스트 LLM 호출에 연결한다. 두 백엔드에서 서로 다른 방식으로 "같은 도구"를 제공한다:
  - "cli" : call_claude 에 --mcp-config(.mcp.json)+--allowedTools 를 넘긴다. claude -p 프로세스
            자체가 MCP 클라이언트 역할을 해서 도구 호출~응답 루프를 내부적으로 처리한다.
  - "api" : Anthropic API 는 로컬 stdio MCP 서버에 직접 붙을 수 없어(원격 HTTP/SSE MCP 커넥터만
            지원), evaluation.creative.reference_retrieval 의 같은 함수를 Anthropic 네이티브
            tool_use 스키마로 직접 노출하고 이 파일이 도구 호출~응답 루프를 수동으로 돈다
            (evaluation/creative/reference_retrieval.py 의 TOOL_DEFINITIONS/call_tool 재사용 —
            검색 로직 자체는 두 백엔드가 완전히 동일하고 전송 방식만 다르다).
"""
from __future__ import annotations

import contextvars
import json
import logging
import os
import tempfile
from pathlib import Path

from utils.env_loader import load_env
from utils.json_utils import parse_json
from utils.llm_caller import call_claude
from utils.openai_caller import call_openai_with_images

logger = logging.getLogger(__name__)

_VALID_BACKENDS = ("cli", "api")
_backend: contextvars.ContextVar[str] = contextvars.ContextVar("v5_m0_m3_llm_backend", default="cli")
_retrieval: contextvars.ContextVar[bool] = contextvars.ContextVar("v5_m0_m3_llm_retrieval", default=False)
_retrieval_log: contextvars.ContextVar[str | None] = contextvars.ContextVar("v5_m0_m3_llm_retrieval_log", default=None)

# evaluation.creative.reference_retrieval 이 읽는 환경변수 이름과 반드시 일치해야 한다 — 그 모듈이
# "어떤 단계가 호출했는지" 로그에 남기는 유일한 통로다(MCP 서브프로세스 경유든 API 인프로세스
# 툴콜이든 이 두 환경변수만 셋업하면 동일하게 동작). generation/v5_m0_m3/README.md 참고.
_RR_LOG_PATH_ENV = "REFERENCE_RETRIEVAL_LOG_PATH"
_RR_LOG_STAGE_ENV = "REFERENCE_RETRIEVAL_LOG_STAGE"

_CLI_DEFAULT_TIMEOUT = 300
_CLI_TIMEOUT_MULTIPLIER = 2  # cli(서브프로세스) 백엔드는 api 대비 느릴 수 있어 기본 timeout 2배

_API_DEFAULT_MODEL = "claude-sonnet-5"
# M3 는 컨셉 5~8개 × 필드 10개(+referencedvideoid/referencedelement) 라 8000 이면 컨셉 7개
# 근처에서 max_tokens 로 잘릴 수 있다(실측: retrieval 켜고 2회 검색+인용 근거까지 채우니 초과).
_API_MAX_TOKENS = 12000
_API_TOOL_ROUNDS = 4  # tool_use 왕복 최대 횟수(무한루프 방지) — 다 써도 답이 없으면 parse_failed
_JSON_FORCE_INSTRUCTION = (
    "\n\n[OUTPUT FORMAT — STRICT]\n"
    "Reply with ONLY a single valid JSON object.\n"
    "No markdown code fences, no preamble, no trailing text, no explanations.\n"
    "Start with { and end with }."
)

# .mcp.json 은 저장소 루트에 있다 — 이 파일은 generation/v5_m0_m3/ 아래라 parents[2].
_MCP_CONFIG_PATH = str(Path(__file__).resolve().parents[2] / ".mcp.json")
_MCP_SERVER_NAME = "creative-retrieval"
_MCP_ALLOWED_TOOLS = [
    f"mcp__{_MCP_SERVER_NAME}__search_reference_ads",
    f"mcp__{_MCP_SERVER_NAME}__list_segment_columns",
]

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


def set_retrieval(enabled: bool) -> None:
    """크리에이티브 벡터 DB 참조 광고 검색 도구(creative-retrieval MCP) 사용 여부.

    CLI 진입점이 --retrieval 플래그를 받아 실행 시작 시 1회 호출한다. 기본 False(기존 동작 무변화).
    """
    _retrieval.set(bool(enabled))


def get_retrieval() -> bool:
    return _retrieval.get()


def set_retrieval_log(path: str | Path | None) -> None:
    """참조 광고 검색 도구 호출 기록(JSONL)을 남길 경로. None 이면 로깅하지 않는다(기본).

    cli.py 가 --retrieval 일 때 output_dir/<slug>_retrieval.jsonl 로 설정한다. 실제 기록은
    evaluation.creative.reference_retrieval 이 담당 — 이 함수는 그 모듈이 읽는 환경변수를
    셋업할 뿐이다(cli/api 백엔드 모두 같은 방식으로 동작하게 하는 단일 지점, 모듈 docstring 참고).
    """
    _retrieval_log.set(str(path) if path else None)


def _sync_retrieval_env(stage: str) -> None:
    """chat_json 호출 직전에 부른다 — retrieval 이 꺼져 있거나 로그 경로 미지정이면 아무것도 안 한다."""
    if not get_retrieval():
        return
    log_path = _retrieval_log.get()
    if not log_path:
        return
    os.environ[_RR_LOG_PATH_ENV] = log_path
    os.environ[_RR_LOG_STAGE_ENV] = stage


def _anthropic_api_key() -> str:
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


def _text_of(msg) -> str:
    return "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")


def _chat_json_api(system: str, user: str) -> dict:
    """Anthropic Messages API 직접 호출. json_mode 는 response_format 이 없어 프롬프트 강제 + 파싱 복구로 대신한다."""
    if get_retrieval():
        return _chat_json_api_with_tools(system, user)
    client = _get_anthropic_client()
    msg = client.messages.create(
        model=_API_DEFAULT_MODEL,
        max_tokens=_API_MAX_TOKENS,
        system=system + _JSON_FORCE_INSTRUCTION,
        messages=[{"role": "user", "content": user}],
    )
    return parse_json(_text_of(msg))


def _chat_json_api_with_tools(system: str, user: str) -> dict:
    """retrieval 활성 시의 Anthropic tool_use 루프 — creative-retrieval 도구를 네이티브 함수콜로 제공.

    MCP 프로토콜을 타지 않고 evaluation.creative.reference_retrieval 을 직접 호출한다(같은 검색
    로직, 다른 전송 방식 — 모듈 docstring 참고). 모델이 tool_use 를 멈추고 텍스트로 답할 때까지
    최대 _API_TOOL_ROUNDS 회 왕복한다.
    """
    from evaluation.creative.reference_retrieval import TOOL_DEFINITIONS, call_tool

    client = _get_anthropic_client()
    messages: list[dict] = [{"role": "user", "content": user}]
    msg = None
    for _ in range(_API_TOOL_ROUNDS):
        msg = client.messages.create(
            model=_API_DEFAULT_MODEL,
            max_tokens=_API_MAX_TOKENS,
            system=system + _JSON_FORCE_INSTRUCTION,
            messages=messages,
            tools=TOOL_DEFINITIONS,
        )
        if msg.stop_reason != "tool_use":
            return parse_json(_text_of(msg))

        messages.append({"role": "assistant", "content": msg.content})
        tool_results = []
        for block in msg.content:
            if getattr(block, "type", "") == "tool_use":
                try:
                    result = call_tool(block.name, block.input or {})
                except Exception as e:
                    result = {"error": f"{type(e).__name__}: {e}"}
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })
        messages.append({"role": "user", "content": tool_results})

    text = _text_of(msg) if msg else ""
    return parse_json(text) if text else {"error": "parse_failed", "raw": "tool_use round 소진, 최종 답변 없음"}


def _chat_json_cli(system: str, user: str, *, timeout: int) -> dict:
    prompt = f"{system}\n\n---\n\n{user}\n\n위 입력으로 지시를 수행하고, JSON 객체 하나로만 응답하세요."
    kwargs: dict = {"timeout": timeout * _CLI_TIMEOUT_MULTIPLIER}
    if get_retrieval():
        kwargs["mcp_config"] = _MCP_CONFIG_PATH
        kwargs["allowed_tools"] = _MCP_ALLOWED_TOOLS
    return call_claude(prompt, **kwargs)


def chat_json(system: str, user: str, *, timeout: int = _CLI_DEFAULT_TIMEOUT, stage: str = "") -> dict:
    """system+user 프롬프트를 현재 백엔드(get_backend())로 실행하고 JSON dict 를 반환한다.

    timeout 은 "cli" 백엔드에만 적용되며(위 docstring 참고), 실제로는 이 값의
    _CLI_TIMEOUT_MULTIPLIER(2)배가 call_claude 에 전달된다. "api" 백엔드는 SDK 기본
    타임아웃을 쓴다. 실패해도 예외를 던지지 않고 {"error": "parse_failed", ...} 를 반환한다
    (utils.json_utils.parse_json 계약 — 호출부가 빈 결과로 graceful 처리).

    stage: 이 호출을 낸 파이프라인 단계 라벨(예: "M1", "M0:material_analysis") — retrieval 사용
    로그(set_retrieval_log)에 "어느 단계가 검색했는지" 기록하는 용도. retrieval 이 꺼져 있거나
    로그 경로가 없으면 무시된다.
    """
    _sync_retrieval_env(stage)
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
