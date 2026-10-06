# ChromaDB RAG MCP 서버 시작 스크립트.
# env/python.env 에서 VENV_PATH 를 읽어 Python 경로를 결정한다.
$root    = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$envFile = Join-Path $root "env\python.env"

if (-not (Test-Path $envFile)) {
    throw "env/python.env 를 찾을 수 없습니다: $envFile"
}

Get-Content $envFile | Where-Object { $_ -match '^\s*[^#]\w+=' } | ForEach-Object {
    if ($_ -match '^(\w+)\s*=\s*"?([^"]*)"?$') {
        [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
    }
}

$python = Join-Path $env:VENV_PATH "Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Python 실행 파일을 찾을 수 없습니다: $python"
}

Set-Location $root
& $python -m database.server.mcp_server
