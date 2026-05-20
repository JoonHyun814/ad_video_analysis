# setup_venv.ps1
# python.env 의 PYTHON_PATH / VENV_PATH 를 읽어 가상환경을 생성합니다.

$envFile = Join-Path $PSScriptRoot "env\python.env"

if (-not (Test-Path $envFile)) {
    Write-Error "env\python.env 파일을 찾을 수 없습니다: $envFile"
    exit 1
}

# .env 파싱 (주석 제외, KEY="VALUE" 형식)
$config = @{}
Get-Content $envFile | Where-Object { $_ -match '^\s*[^#]\S+=.+' } | ForEach-Object {
    $parts = $_ -split '=', 2
    $key   = $parts[0].Trim()
    $value = $parts[1].Trim().Trim('"')
    $config[$key] = $value
}

$pythonPath = $config['PYTHON_PATH']
$venvPath   = $config['VENV_PATH']

if (-not $pythonPath -or -not $venvPath) {
    Write-Error "PYTHON_PATH 또는 VENV_PATH 값을 읽지 못했습니다."
    exit 1
}

Write-Host "Python : $pythonPath"
Write-Host "Venv   : $venvPath"

# Python 실행파일 존재 확인
if (-not (Test-Path $pythonPath)) {
    Write-Error "Python 실행파일을 찾을 수 없습니다: $pythonPath"
    exit 1
}

# 이미 가상환경이 있으면 스킵
if (Test-Path (Join-Path $venvPath "Scripts\python.exe")) {
    Write-Host "가상환경이 이미 존재합니다: $venvPath"
    exit 0
}

# 가상환경 생성
Write-Host "가상환경을 생성합니다..."
& $pythonPath -m venv $venvPath
if ($LASTEXITCODE -ne 0) {
    Write-Error "가상환경 생성 실패"
    exit 1
}

Write-Host "가상환경 생성 완료: $venvPath"

# ── 패키지 설치 ──────────────────────────────────────────────
# 패키지를 추가하거나 제거할 때 이 목록도 함께 수정한다.
$pip = Join-Path $venvPath "Scripts\pip.exe"

Write-Host "패키지를 설치합니다..."
& $pip install --upgrade pip | Out-Null
& $pip install mysql-connector-python
if ($LASTEXITCODE -ne 0) {
    Write-Error "패키지 설치 실패"
    exit 1
}
# ─────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "활성화 명령:"
Write-Host "  . $venvPath\Scripts\Activate.ps1"
