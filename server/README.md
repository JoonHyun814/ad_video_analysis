# server 모듈

내부망(사내망)에서 다른 머신이 접속할 수 있는 **네트워크용 MCP 서버**. 이 저장소의 유일한
ChromaDB MCP 도구(`search_chromadb`)를 Streamable HTTP 전송으로 노출한다.

`db/chromadb/mcp_server.py`(stdio, 로컬 `claude -p` 전용, 저장소 루트 `.mcp.json` 등록)와
도구·검색 로직은 완전히 같다 — 둘 다 `db.chromadb.tool_definitions.search_chromadb` 를 그대로
가져다 쓰는 얇은 전송 계층이다. 이 서버는 그 stdio 서버를 대체하지 않고 **병행 운영**된다:

| | `db/chromadb/mcp_server.py` | `server/mcp_server.py` |
|---|---|---|
| 전송 | stdio (subprocess) | Streamable HTTP |
| 대상 | 이 저장소 안에서 로컬로 뜨는 `claude -p`/대화형 세션 | 내부망의 다른 머신, Anthropic API 원격 MCP 커넥터 등 |
| 등록 | 저장소 루트 `.mcp.json` (`chromadb-explorer`) | 접속하는 쪽이 `url` 로 직접 등록 |
| 인증 | 해당 없음(로컬 프로세스 직속) | 없음(내부망 신뢰 전제 — 아래 "보안" 참고) |

## 실행

`ad_video_analysis/` 디렉토리에서 실행한다.

```bash
python -m server.mcp_server
```

기본으로 `0.0.0.0:8765` 에 바인딩해 모든 인터페이스에서 접속을 받는다. 포트는
`MCP_SERVER_PORT` 환경변수로 바꿀 수 있다.

```bash
MCP_SERVER_PORT=9000 python -m server.mcp_server
```

기동 시 임베딩 모델(`BAAI/bge-m3`)을 미리 로드한다(`db.chromadb.connection.get_embedding_function`)
— 첫 검색 요청이 모델 로딩 비용까지 떠안아 느려지거나 타임아웃에 걸리는 것을 피하기 위함이다.
로딩이 끝나면 콘솔에 접속 URL을 출력한다.

## 도구

`search_chromadb` 하나만 노출한다 — `db/chromadb/mcp_server.py`, `db/README.md`의
"MCP 서버 / Claude API 도구" 절과 동일한 스키마다.

| 도구 | 인자 | 반환 |
|------|------|------|
| `search_chromadb` | `collection`(필수), `query_text`(필수, 자연어), `n_results`(기본 5), `log_prefix`(기본 `"default"`) | 유사도 상위 레코드 |

호출 로깅도 동일하게 항상 켜져 있다(`<log_root>/<log_prefix>.jsonl`, 기본
`logs/search_chromadb/<날짜>/`, `SEARCH_CHROMADB_LOG_DIR` 환경변수로 재지정 가능 — 자세한
내용은 `db/README.md` 참고).

## 클라이언트 등록 (내부망의 다른 프로젝트/서버)

Streamable HTTP MCP 서버이므로 `command` 대신 `url` 로 등록한다:

```json
{
  "mcpServers": {
    "chromadb-explorer-network": {
      "type": "http",
      "url": "http://<이 서버가 도는 내부망 호스트>:8765/mcp"
    }
  }
}
```

Anthropic API(Claude API)에서 네이티브 MCP 커넥터로 직접 붙일 수도 있다 — 로컬 stdio MCP
서버(`db/chromadb/mcp_server.py`)와 달리 이 서버는 원격 HTTP 서버라 API 가 직접 붙을 수
있다는 점이 두 서버의 핵심 차이다(`generation/v5_m0_m3/llm_adapter.py` 모듈 docstring 참고).

## 보안

인증 없이 `0.0.0.0` 에 바인딩한다 — **내부망(사내망)이 방화벽/VPN 으로 이미 외부와 분리돼
있다는 전제**로 설계했다. 외부 인터넷에 노출되는 호스트에서 이 서버를 띄우지 말 것. 접속 주체를
제한해야 하면(예: 사내망이라도 특정 서버에서만 접속 허용) 이 서버 앞단에 리버스 프록시를 두고
인증/IP 허용목록을 적용하거나, 네트워크 방화벽 규칙으로 8765 포트 접근을 제한한다 — 이 서버
자체는 토큰 검증 로직을 두지 않는다.
