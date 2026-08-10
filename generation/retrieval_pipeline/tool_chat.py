"""retrieval_pipeline 전용 — LLM이 db.chromadb.tool_definitions.search_chromadb 를 tool_use 로
자율 호출(몇 번이든, 어느 컬렉션을 언제 검색할지 스스로 판단)하며 최종 JSON 응답을 완성하는
왕복 루프.

generation.v5_m0_m3.llm_adapter 는 stage 별로 고정된 kind(concept/production)에 맞춰 도구와
컬렉션명을 미리 정해준다 — 이 파이프라인은 매 검색 호출마다 category_analysis/scenario_analysis
둘 중 어느 쪽을 쓸지 LLM 이 스스로 판단해야 해서 그 인프라를 그대로 쓰지 않고 이 파일에
독립적으로 둔다(노출하는 도구 자체가 이미 컬렉션명을 인자로 받는 범용 `search_chromadb`
하나뿐이라 kind 배정이 필요 없다).

  - "cli": utils.llm_caller.call_claude 에 --mcp-config(.mcp.json)+--allowedTools 로
    chromadb-explorer MCP 서버 하나만 열어준다 — claude -p 프로세스 자체가 도구 왕복을
    내부적으로 처리하므로 이 함수는 1회 서브프로세스 호출로 끝난다.
  - "api": Anthropic Messages API 를 db.chromadb.tool_definitions.TOOL_DEFINITIONS 와 함께
    직접 호출하고, stop_reason == "tool_use" 인 동안 이 파일이 직접 왕복한다(로컬 stdio MCP
    서버에 API 가 못 붙는 이유는 generation/v5_m0_m3/llm_adapter.py 모듈 docstring 참고).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from db.chromadb.tool_definitions import TOOL_DEFINITIONS, call_tool
from utils.env_loader import load_env
from utils.json_utils import parse_json
from utils.llm_caller import call_claude

_MCP_CONFIG_PATH = str(Path(__file__).resolve().parents[2] / ".mcp.json")
_MCP_ALLOWED_TOOLS = ["mcp__chromadb-explorer__search_chromadb"]

# db.chromadb.tool_definitions 가 읽는 환경변수 이름과 반드시 일치해야 한다 — search_chromadb
# 호출 로그를 이 실행의 출력 폴더로 몰아넣는 유일한 통로다(도구 스키마에 log_root 인자를 두지
# 않은 이유는 tool_definitions.py 모듈 docstring 참고).
_LOG_DIR_ENV = "SEARCH_CHROMADB_LOG_DIR"

_API_DEFAULT_MODEL = "claude-sonnet-5"
_API_MAX_TOKENS = 24000
_API_TOOL_ROUNDS = 8  # 장치 8개 근거를 컬렉션 2개에 걸쳐 여러 쿼리로 모을 수 있어 여유 있게 잡음
_RETRY_DELAYS = (30, 60, 120)
_JSON_FORCE_INSTRUCTION = (
    "\n\n[OUTPUT FORMAT — STRICT]\n"
    "Reply with ONLY a single valid JSON object.\n"
    "No markdown code fences, no preamble, no trailing text, no explanations.\n"
    "Start with { and end with }."
)

_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY") or (load_env("env/api.env").get("ANTHROPIC_API_KEY") or "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY가 환경변수나 env/api.env에서 발견되지 않았습니다.")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def _text_of(msg) -> str:
    return "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")


def _create_message(**kwargs):
    """529 과부하만 재시도한다(그 외 예외는 그대로 올린다) — utils.claude_api_caller 와 동일 정책."""
    for attempt, delay in enumerate((*_RETRY_DELAYS, None), start=1):
        try:
            with _get_client().messages.stream(**kwargs) as stream:
                return stream.get_final_message()
        except Exception as e:
            if not ("529" in str(e) or "overloaded" in str(e).lower()) or delay is None:
                raise
            print(f"      Claude API overloaded, retrying in {delay}s ({attempt}/{len(_RETRY_DELAYS)})...")
            time.sleep(delay)


def _run_api(system: str, user: str, *, log_prefix: str) -> dict:
    messages: list[dict] = [{"role": "user", "content": user}]
    msg = None
    for _ in range(_API_TOOL_ROUNDS):
        msg = _create_message(
            model=_API_DEFAULT_MODEL, max_tokens=_API_MAX_TOKENS,
            system=system + _JSON_FORCE_INSTRUCTION, messages=messages, tools=TOOL_DEFINITIONS,
        )
        if msg.stop_reason != "tool_use":
            return parse_json(_text_of(msg))
        messages.append({"role": "assistant", "content": msg.content})
        tool_results = []
        for block in msg.content:
            if getattr(block, "type", "") == "tool_use":
                args = {**(block.input or {})}
                if block.name == "search_chromadb":
                    args["log_prefix"] = log_prefix  # 모델이 프롬프트 지시를 어겨도 항상 강제
                try:
                    result = call_tool(block.name, args)
                except Exception as e:
                    result = {"error": f"{type(e).__name__}: {e}"}
                tool_results.append({
                    "type": "tool_result", "tool_use_id": block.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })
        messages.append({"role": "user", "content": tool_results})
    text = _text_of(msg) if msg else ""
    return parse_json(text) if text else {"error": "parse_failed", "raw": "tool_use round 소진, 최종 답변 없음"}


def _run_cli(system: str, user: str, *, timeout: int) -> dict:
    """MCP(chromadb-explorer) 왕복은 claude -p 서브프로세스 내부에서 일어나 여기서 tool_use
    블록을 가로챌 수 없다 — log_prefix 는 system 프롬프트 지시(m3_system.md)에만 의존한다."""
    prompt = f"{system}\n\n---\n\n{user}\n\n위 입력으로 지시를 수행하고, JSON 객체 하나로만 응답하세요."
    return call_claude(prompt, timeout=timeout, mcp_config=_MCP_CONFIG_PATH, allowed_tools=_MCP_ALLOWED_TOOLS)


def run(system: str, user: str, *, backend: str, log_prefix: str = "default",
       log_dir: str | Path | None = None, timeout: int = 600) -> dict:
    """system+user 프롬프트를 backend("cli"|"api")로 실행하고, search_chromadb 도구를 자율
    호출하며 완성한 최종 JSON 응답을 반환한다.

    log_prefix: search_chromadb 호출 로그 파일명(<log_prefix>.jsonl). "api" 백엔드는 여기서
    강제 적용되고, "cli"(MCP) 백엔드는 system 프롬프트 지시로만 전달된다(위 _run_cli 참고).
    log_dir: 로그를 남길 폴더(기본 None → tool_definitions.py 의 기본값 logs/search_chromadb/).
    지정하면 SEARCH_CHROMADB_LOG_DIR 환경변수로 이 호출 동안만 덮어쓰고 끝나면 원래대로
    되돌린다(같은 프로세스에서 여러 번 run() 을 호출해도 서로 새지 않도록).
    """
    prev = os.environ.get(_LOG_DIR_ENV)
    if log_dir is not None:
        os.environ[_LOG_DIR_ENV] = str(log_dir)
    try:
        if backend == "api":
            return _run_api(system, user, log_prefix=log_prefix)
        return _run_cli(system, user, timeout=timeout)
    finally:
        if log_dir is not None:
            if prev is None:
                os.environ.pop(_LOG_DIR_ENV, None)
            else:
                os.environ[_LOG_DIR_ENV] = prev
