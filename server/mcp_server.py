"""chromadb-explorer-network — `search_chromadb` 하나만 노출하는 내부망용 Streamable HTTP MCP 서버.

`db/chromadb/mcp_server.py`(stdio, 로컬 `claude -p` 전용)와 도구·검색 로직은 완전히 동일하다 —
`db.chromadb.tool_definitions.search_chromadb` 를 그대로 재사용하고 전송 계층만 stdio →
Streamable HTTP 로 바꿨다. 로컬 subprocess 스폰 없이 내부망의 다른 머신(다른 서버, Anthropic
API 원격 MCP 커넥터 등— 로컬 stdio MCP 서버에는 API 가 직접 붙을 수 없다는 제약이 이 서버에는
적용되지 않는다)이 HTTP 로 접속할 수 있게 하는 것이 목적이다.

기존 stdio 서버(`.mcp.json` 의 `chromadb-explorer`)는 그대로 둔다 — 이 서버는 그것을
대체하지 않고 병행 운영된다(로컬 `claude -p` 세션은 계속 stdio 서버를 쓴다).

바인딩: 기본 `0.0.0.0`(모든 인터페이스) — 내부망(사내망) 신뢰를 전제로 별도 인증 없이 연다.
외부 인터넷에 노출하지 않도록 방화벽/네트워크 경계에서 반드시 접근을 내부망으로 제한할 것.
포트: 기본 8765, `MCP_SERVER_PORT` 환경변수로 변경 가능. `stateless_http=True` — 요청마다
독립적인 세션으로 처리해(서버가 세션 상태를 들고 있지 않음) 여러 머신이 동시에 접속해도
세션 어피니티 문제가 없다.

호출마다 `<log_prefix>.jsonl` 에 로그가 남는다(기본 위치 `logs/search_chromadb/<날짜>/`,
호출측이 `SEARCH_CHROMADB_LOG_DIR` 환경변수로 재지정 가능 — `db/chromadb/tool_definitions.py`
참고). `list_collections`/`show_schema`/`show_by_video_id`/`importers/*`(컬렉션 조회·삭제·
재적재)는 도구로 올리지 않는다 — 사람이 CLI로 직접 실행한다.

로컬 실행:
    python -m server.mcp_server
    MCP_SERVER_PORT=9000 python -m server.mcp_server

내부망 클라이언트 등록 예시(원격 MCP — 이 저장소가 아닌 다른 프로젝트/서버의 `.mcp.json`):
    {
      "mcpServers": {
        "chromadb-explorer-network": {
          "type": "http",
          "url": "http://<이 서버가 도는 내부망 호스트>:8765/mcp"
        }
      }
    }
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from db.chromadb.tool_definitions import search_chromadb as _search_chromadb

_DEFAULT_PORT = 8765
_HOST = "0.0.0.0"

mcp = FastMCP(
    "chromadb-explorer-network",
    host=_HOST,
    port=int(os.environ.get("MCP_SERVER_PORT", _DEFAULT_PORT)),
    stateless_http=True,
)


@mcp.tool()
def search_chromadb(collection: str, query_text: str, n_results: int = 5, log_prefix: str = "default") -> dict:
    """컬렉션 하나를 지정하고 자연어 쿼리로 유사도 검색한다(임베딩: BAAI/bge-m3, 한/영 모두
    잘 동작). 호출마다 <log_prefix>.jsonl 에 기록된다(기본 위치 logs/search_chromadb/<날짜>/).

    Args:
        collection: 검색할 컬렉션명(예: ad_concept_reference, ad_production_reference,
            category_analysis, scenario_analysis, video_category).
        query_text: 자연어 검색 쿼리(자유 서술 문장이 항상 안전).
        n_results: 반환 결과 수(기본 5).
        log_prefix: 호출 로그 파일명(<log_prefix>.jsonl) — 이 호출이 어떤 맥락(프로젝트/단계명
            등)에서 나왔는지 표시한다. 미지정 시 'default'.
    """
    return _search_chromadb(collection, query_text, n_results, log_prefix)


def main() -> None:
    # 임베딩 모델(bge-m3) 로딩을 서버 기동 시점에 미리 치른다 — stdio 서버(db/chromadb/mcp_server.py)와
    # 동일한 이유(첫 요청이 모델 로딩까지 떠안아 타임아웃에 걸리는 것을 피하기 위함).
    from db.chromadb.connection import get_embedding_function
    get_embedding_function()
    url = f"http://{_HOST}:{mcp.settings.port}{mcp.settings.streamable_http_path}"
    print(f"chromadb-explorer-network MCP 서버 기동: {url} (내부망 바인딩, 인증 없음)")
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
