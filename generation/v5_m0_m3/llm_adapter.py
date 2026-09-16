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

[신규] set_retrieval(True) — 참조 벡터 DB 검색을 텍스트 LLM 호출에 연결한다. **두 백엔드가
더 이상 완전히 같은 기능을 제공하지 않는다**(chromadb-explorer MCP 서버가 범용 도구
`search_chromadb` 하나만 노출하도록 축소된 이후):
  - "cli" : call_claude 에 --mcp-config(.mcp.json)+--allowedTools 를 넘겨 `chromadb-explorer`
            MCP 서버(db/chromadb/mcp_server.py)의 `search_chromadb(collection, query_text,
            n_results, log_prefix)` 하나만 연다. 이 도구는 segment_column 필터·
            self-reference 정책·notable_elements 를 모르는 순수 자연어 검색이라, kind 에
            맞는 컬렉션명(`_MCP_COLLECTION_BY_KIND`)을 프롬프트에 안내문으로 덧붙여 알려준다
            (`_chat_json_cli`). claude -p 프로세스 자체가 MCP 클라이언트 역할을 한다.
  - "api" : Anthropic API 는 로컬 stdio MCP 서버에 직접 붙을 수 없어(원격 HTTP/SSE MCP 커넥터만
            지원), db.chromadb.creative_search 의 `search_concept_reference`/
            `search_production_reference`(segment 필터·self-reference 정책·notable_elements
            포함, MCP 축소와 무관하게 그대로 유지됨)를 Anthropic 네이티브 tool_use 스키마로
            직접 노출하고 이 파일이 도구 호출~응답 루프를 수동으로 돈다(db/chromadb/
            creative_search.py 의 TOOL_DEFINITIONS_*/call_tool 재사용) — **api 백엔드가 cli
            백엔드보다 더 풍부한 검색 기능을 쓴다.**

도구는 stage 별로 정확히 한 종류만 노출한다(_STAGE_TOOL_KIND) — M3·M3_LENS_SCOUT(M3 발산
직전 사전 조사, modules_runner._scout_emergent_lenses 참고)는 ad_concept_reference 검색
도구(concept), M4~M9·STORYBOARD_HTML 은 ad_production_reference 검색 도구(production),
M1/M2 는 retrieval 이 켜져 있어도 도구를 받지 않는다. 두 용도를 동시에 열어주지 않는다
(evaluation/README.md 스키마 통합 계획 참고).
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
_self_video_id: contextvars.ContextVar[int | None] = contextvars.ContextVar("v5_m0_m3_self_video_id", default=None)
_self_mode: contextvars.ContextVar[str] = contextvars.ContextVar("v5_m0_m3_self_mode", default="")

# db.chromadb.creative_search 이 읽는 환경변수 이름과 반드시 일치해야 한다 — 그 모듈이
# "어떤 단계가 호출했는지" 로그에 남기는 유일한 통로다(MCP 서브프로세스 경유든 API 인프로세스
# 툴콜이든 이 두 환경변수만 셋업하면 동일하게 동작). generation/v5_m0_m3/README.md 참고.
_RR_LOG_PATH_ENV = "REFERENCE_RETRIEVAL_LOG_PATH"
_RR_LOG_STAGE_ENV = "REFERENCE_RETRIEVAL_LOG_STAGE"
# db.chromadb.creative_search 의 self-reference 정책(restore/exclude) 환경변수 이름과
# 반드시 일치해야 한다 — 기존 방영 광고를 M3 로 재추출해 M4~M9 를 돌릴 때만 쓰는 옵션(위 모듈
# docstring, generation/v5_m0_m3/existing_ad_adapter.py 참고). 일반 URL 소재 파이프라인은 이
# 두 값을 설정하지 않으므로 동작이 전혀 바뀌지 않는다.
_RR_SELF_VIDEO_ID_ENV = "REFERENCE_RETRIEVAL_SELF_VIDEO_ID"
_RR_SELF_MODE_ENV = "REFERENCE_RETRIEVAL_SELF_MODE"

_CLI_DEFAULT_TIMEOUT = 300
_CLI_TIMEOUT_MULTIPLIER = 2  # cli(서브프로세스) 백엔드는 api 대비 느릴 수 있어 기본 timeout 2배

_API_DEFAULT_MODEL = "claude-sonnet-5"
# M3 는 컨셉 5~8개 × 필드 10개(+referencedvideoid/referencedelement) 라 8000 이면 컨셉 7개
# 근처에서 max_tokens 로 잘릴 수 있다(실측: retrieval 켜고 2회 검색+인용 근거까지 채우니 초과).
# 렌즈별 타겟 검색(모듈 안내문 참고)으로 검색 결과가 여러 건 쌓이면 모델이 그 결과를 종합하는
# 데 쓰는 thinking 토큰이 급격히 늘어 max_tokens 를 그대로 잡아먹는 사례가 실측됐다(12000 중
# thinking 11389 소모 -> 정작 JSON 답변이 다 못 나오고 잘림). thinking+답변을 모두 감당하도록
# 여유 있게 잡는다.
_API_MAX_TOKENS = 24000
# tool_use 왕복 최대 횟수(무한루프 방지) — 다 써도 답이 없으면 parse_failed. M3 는 렌즈별로
# 나눠 여러 번 검색하도록 유도하므로(모듈 안내문 참고) 4 는 부족할 수 있어 여유를 뒀다 —
# 한 라운드에 tool_use 블록을 여러 개 담아 보내는 것도 가능하니 실제로는 라운드 부족보다
# 여유 있는 편이 안전하다.
_API_TOOL_ROUNDS = 6
_JSON_FORCE_INSTRUCTION = (
    "\n\n[OUTPUT FORMAT — STRICT]\n"
    "Reply with ONLY a single valid JSON object.\n"
    "No markdown code fences, no preamble, no trailing text, no explanations.\n"
    "Start with { and end with }."
)

# .mcp.json 은 저장소 루트에 있다 — 이 파일은 generation/v5_m0_m3/ 아래라 parents[2].
_MCP_CONFIG_PATH = str(Path(__file__).resolve().parents[2] / ".mcp.json")
_MCP_SERVER_NAME = "chromadb-explorer"
# chromadb-explorer 는 이제 도구가 search_chromadb 하나뿐이라(collection 인자로 컬렉션을
# 직접 지정) kind 별로 다른 도구를 열어줄 필요가 없다 — 대신 kind 에 맞는 컬렉션명을
# _chat_json_cli 가 프롬프트에 안내문으로 덧붙인다(_MCP_COLLECTION_BY_KIND).
_MCP_ALLOWED_TOOLS_BY_KIND: dict[str, list[str]] = {
    "concept": [f"mcp__{_MCP_SERVER_NAME}__search_chromadb"],
    "production": [f"mcp__{_MCP_SERVER_NAME}__search_chromadb"],
}
_MCP_COLLECTION_BY_KIND: dict[str, str] = {
    "concept": "ad_concept_reference",
    "production": "ad_production_reference",
}

# stage(chat_json 호출자가 넘기는 "M3" 등 라벨) → 노출할 검색 도구 종류. 없는 stage(M1/M2 등)는
# retrieval 이 켜져 있어도 도구를 받지 않는다 — M3=컨셉 발산 참고, M4~M9/STORYBOARD_HTML=연출 참고.
_STAGE_TOOL_KIND: dict[str, str] = {
    "M3": "concept", "M3_LENS_SCOUT": "concept",
    "M4": "production", "M5": "production", "M6": "production",
    "M7": "production", "M9": "production",
    "STORYBOARD_HTML": "production",
}


def _tool_kind_for_stage(stage: str) -> str | None:
    if not get_retrieval():
        return None
    return _STAGE_TOOL_KIND.get(stage)

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
    db.chromadb.creative_search 이 담당 — 이 함수는 그 모듈이 읽는 환경변수를
    셋업할 뿐이다(cli/api 백엔드 모두 같은 방식으로 동작하게 하는 단일 지점, 모듈 docstring 참고).
    """
    _retrieval_log.set(str(path) if path else None)


def set_self_reference(video_id: int | None, mode: str = "restore") -> None:
    """검색 결과에 분석 대상 광고 자기 자신(video_id)이 걸렸을 때의 처리 방식을 지정한다.

    기존 방영 광고를 M3 로 재추출해 M4~M9 를 돌리는 실험(generation/v5_m0_m3/
    existing_ad_adapter.py) 전용 — video_id 를 안 주면(None) 기본 동작 그대로라 일반 URL 소재
    파이프라인에는 영향 없다.
      mode="restore": 자기 자신이 검색되면 db.chromadb.creative_search 이 실제
        scenario_analysis/production_analysis 원본(cast/scenes/elements)을 결과에 덧붙이고
        "새로 창작하지 말고 그대로 재현하라"는 지시를 함께 반환한다 — self-reference 가 원본
        복원 수준까지 도달할 수 있는지 검증하는 용도.
      mode="exclude": 자기 자신을 검색 결과에서 아예 제외한다 — self-hit 없이 순수 타 광고
        레퍼런스만으로 돌렸을 때를 보는 ablation.
    """
    _self_video_id.set(video_id)
    _self_mode.set(mode if video_id is not None else "")


def get_self_reference() -> tuple[int | None, str]:
    return _self_video_id.get(), _self_mode.get()


def _sync_retrieval_env(stage: str) -> None:
    """chat_json 호출 직전에 부른다."""
    self_id, self_mode = get_self_reference()
    if self_id is not None and self_mode:
        os.environ[_RR_SELF_VIDEO_ID_ENV] = str(self_id)
        os.environ[_RR_SELF_MODE_ENV] = self_mode
    else:
        os.environ.pop(_RR_SELF_VIDEO_ID_ENV, None)
        os.environ.pop(_RR_SELF_MODE_ENV, None)

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


def _create_message(**kwargs):
    """client.messages.create 대신 스트리밍으로 호출한다 — Anthropic SDK 는 max_tokens 기준
    예상 소요시간이 10분을 넘을 수 있으면(_API_MAX_TOKENS=24000 이 여기 해당) 비-스트리밍
    호출을 ValueError 로 거부하고 스트리밍을 요구한다. 여기서 스트리밍으로 받아 최종
    Message 객체만 돌려주면 호출부(stop_reason/content 등 접근)는 기존과 동일하게 쓸 수 있다."""
    client = _get_anthropic_client()
    with client.messages.stream(**kwargs) as stream:
        return stream.get_final_message()


def _chat_json_api(system: str, user: str, stage: str) -> dict:
    """Anthropic Messages API 직접 호출. json_mode 는 response_format 이 없어 프롬프트 강제 + 파싱 복구로 대신한다."""
    kind = _tool_kind_for_stage(stage)
    if kind:
        return _chat_json_api_with_tools(system, user, kind)
    msg = _create_message(
        model=_API_DEFAULT_MODEL,
        max_tokens=_API_MAX_TOKENS,
        system=system + _JSON_FORCE_INSTRUCTION,
        messages=[{"role": "user", "content": user}],
    )
    return parse_json(_text_of(msg))


def _chat_json_api_with_tools(system: str, user: str, kind: str) -> dict:
    """retrieval 활성 시의 Anthropic tool_use 루프 — chromadb-explorer 도구(kind 별 1종)를
    네이티브 함수콜로 제공한다.

    MCP 프로토콜을 타지 않고 db.chromadb.creative_search 를 직접 호출한다(같은 검색
    로직, 다른 전송 방식 — 모듈 docstring 참고). 모델이 tool_use 를 멈추고 텍스트로 답할 때까지
    최대 _API_TOOL_ROUNDS 회 왕복한다.
    """
    from db.chromadb.creative_search import (
        TOOL_DEFINITIONS_CONCEPT, TOOL_DEFINITIONS_PRODUCTION, call_tool,
    )

    tools = TOOL_DEFINITIONS_CONCEPT if kind == "concept" else TOOL_DEFINITIONS_PRODUCTION
    messages: list[dict] = [{"role": "user", "content": user}]
    msg = None
    for _ in range(_API_TOOL_ROUNDS):
        msg = _create_message(
            model=_API_DEFAULT_MODEL,
            max_tokens=_API_MAX_TOKENS,
            system=system + _JSON_FORCE_INSTRUCTION,
            messages=messages,
            tools=tools,
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


def _chat_json_cli(system: str, user: str, *, timeout: int, stage: str) -> dict:
    prompt = f"{system}\n\n---\n\n{user}\n\n위 입력으로 지시를 수행하고, JSON 객체 하나로만 응답하세요."
    kwargs: dict = {"timeout": timeout * _CLI_TIMEOUT_MULTIPLIER}
    kind = _tool_kind_for_stage(stage)
    if kind:
        kwargs["mcp_config"] = _MCP_CONFIG_PATH
        kwargs["allowed_tools"] = _MCP_ALLOWED_TOOLS_BY_KIND[kind]
        # search_chromadb 는 컬렉션명을 직접 받으므로(도구 자체는 어떤 kind 인지 모른다)
        # 이 stage 가 검색해야 할 컬렉션을 프롬프트로 명시한다. log_prefix=stage 로 지정해
        # logs/search_chromadb/<stage>.jsonl 에 단계별로 호출 로그가 쌓이게 한다.
        prompt += (
            f"\n\n[검색 도구 안내] search_chromadb 도구를 쓸 때는 collection=\"{_MCP_COLLECTION_BY_KIND[kind]}\""
            f", log_prefix=\"{stage}\" 로 지정하라."
        )
    return call_claude(prompt, **kwargs)


def chat_json(system: str, user: str, *, timeout: int = _CLI_DEFAULT_TIMEOUT, stage: str = "") -> dict:
    """system+user 프롬프트를 현재 백엔드(get_backend())로 실행하고 JSON dict 를 반환한다.

    timeout 은 "cli" 백엔드에만 적용되며(위 docstring 참고), 실제로는 이 값의
    _CLI_TIMEOUT_MULTIPLIER(2)배가 call_claude 에 전달된다. "api" 백엔드는 SDK 기본
    타임아웃을 쓴다. 실패해도 예외를 던지지 않고 {"error": "parse_failed", ...} 를 반환한다
    (utils.json_utils.parse_json 계약 — 호출부가 빈 결과로 graceful 처리).

    stage: 이 호출을 낸 파이프라인 단계 라벨(예: "M3", "STORYBOARD_HTML"). retrieval 사용
    로그(set_retrieval_log)에 "어느 단계가 검색했는지" 기록하는 용도일 뿐 아니라, _STAGE_TOOL_KIND
    를 통해 "이 단계에 어느 검색 도구를 줄지"(concept/production/없음)도 이 값으로 결정된다.
    """
    _sync_retrieval_env(stage)
    backend = get_backend()
    if backend == "api":
        try:
            return _chat_json_api(system, user, stage)
        except Exception as e:
            logger.warning(f"[llm_adapter] api backend fail, no fallback: {type(e).__name__}: {e}")
            return {"error": "parse_failed", "raw": str(e)}
    return _chat_json_cli(system, user, timeout=timeout, stage=stage)


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
