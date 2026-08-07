"""db/chromadb 가 MCP(`mcp_server.py`)/Anthropic tool_use 양쪽에 노출하는 유일한 도구 —
search_chromadb. 실제 벡터 검색은 `db.chromadb.search_query.search` 를 그대로 재사용하고,
이 파일은 `collection` 명으로 저장 경로를 자동 결정(`db_path_for`)하고 호출 로그를 남기는
얇은 래퍼다.

호출마다 `logs/search_chromadb/<log_prefix>.jsonl` 에 한 줄씩 append 한다 — 에이전트가 언제
어떤 컬렉션을 어떤 쿼리로 검색했는지 파일로 남기기 위함이다(log_prefix 로 호출 맥락을
구분해서 기록한다).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from db.chromadb.search_query import search as _search_impl

_LOG_ROOT = Path(__file__).resolve().parent.parent.parent / "logs" / "search_chromadb"


def _log_call(log_prefix: str, collection: str, query_text: str, n_results: int, result_count: int) -> None:
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "collection": collection,
        "query_text": query_text,
        "n_results": n_results,
        "result_count": result_count,
    }
    try:
        _LOG_ROOT.mkdir(parents=True, exist_ok=True)
        path = _LOG_ROOT / f"{log_prefix or 'default'}.jsonl"
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # 로깅 실패가 검색 자체를 막으면 안 됨


def search_chromadb(collection: str, query_text: str, n_results: int = 5,
                     log_prefix: str = "default") -> dict[str, Any]:
    """컬렉션명(=`data/<collection>/` 저장 경로)으로 자연어 유사도 검색을 실행하고 호출을 기록한다."""
    results = _search_impl(collection, query_text, n_results)
    _log_call(log_prefix, collection, query_text, n_results, len(results))
    return {"collection": collection, "query_text": query_text, "count": len(results), "results": results}


# ── 도구 정의(Anthropic tool_use 스키마) — MCP 서버와 API 백엔드 툴콜 경로가 공유하는 단일 소스 ──

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "search_chromadb",
        "description": (
            "컬렉션 하나를 지정하고 자연어 쿼리로 유사도 검색한다(임베딩: BAAI/bge-m3, 한/영 "
            "모두 잘 동작). query_text 는 자유 서술 문장이 항상 안전하다. 호출마다 로그가 "
            "남으므로 log_prefix 로 이 호출이 어떤 맥락(예: 프로젝트/단계명)에서 나왔는지 "
            "표시하라."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "collection": {"type": "string", "description": "검색할 컬렉션명"},
                "query_text": {"type": "string", "description": "자연어 검색 쿼리"},
                "n_results": {"type": "integer", "description": "반환 결과 수(기본 5)", "default": 5},
                "log_prefix": {"type": "string",
                                "description": "호출 로그 파일명(logs/search_chromadb/<log_prefix>.jsonl). 미지정 시 'default'",
                                "default": "default"},
            },
            "required": ["collection", "query_text"],
        },
    },
]


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """도구 이름 → 함수 디스패치(Anthropic tool_use 루프 전용, MCP 서버는 FastMCP 가 직접 라우팅)."""
    if name == "search_chromadb":
        return search_chromadb(
            arguments["collection"], arguments["query_text"],
            arguments.get("n_results", 5), arguments.get("log_prefix", "default"),
        )
    return {"error": f"unknown tool: {name}"}
