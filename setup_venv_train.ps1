# setup_venv_train.ps1
# train_pipeline 전용 가상환경을 생성한다 (env\python.env 의 PYTHON_PATH / TRAIN_VENV_PATH 사용).
# 일반 파이프라인 venv(.venv, setup_venv.ps1)와 분리하는 이유: unsloth가 설치하는
# torch/transformers 버전이 OCR·STT 등 일반 파이프라인 의존성과 충돌할 수 있기 때문.
#
# 참고: unsloth/bitsandbytes는 리눅스 기준으로 개발되어 네이티브 Windows에서
# 설치·동작이 불안정할 수 있다. 문제가 생기면 WSL2 또는 train_pipeline/Dockerfile 사용을 권장한다.

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
$venvPath   = $config['TRAIN_VENV_PATH']

if (-not $pythonPath -or -not $venvPath) {
    Write-Error "PYTHON_PATH 또는 TRAIN_VENV_PATH 값을 읽지 못했습니다."
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
# train_pipeline/Dockerfile 의 pip install 블록과 동일한 목록을 유지한다.
# 패키지를 추가하거나 제거할 때 두 곳(이 파일 + Dockerfile) 모두 함께 수정한다.
#
# 주의: PyPI 기본 torch 패키지는 Linux는 CUDA wheel을 직접 배포하지만
# Windows는 CPU-only wheel만 배포한다. 게다가 `pip install torch --index-url ...`처럼
# 버전을 안 박고 설치하면 최신판(예: 2.11.0+cu128)이 깔리는데, 이후 unsloth가 요구하는
# 정확한 버전(2.10.0)과 안 맞아 pip가 재설치하면서 로컬 빌드 태그(+cu128) 없이
# 기본 PyPI의 CPU wheel로 조용히 되돌아간다 (실제로 재현 확인함).
# → torch 버전은 unsloth 요구 버전에 맞춰 "+cu128" 태그까지 정확히 박아서 먼저 설치한다.
# unsloth가 향후 다른 torch 버전을 요구하도록 바뀌면 아래 버전 문자열도 같이 갱신해야 한다.
$pip = Join-Path $venvPath "Scripts\pip.exe"
$torchVersion = "2.10.0+cu128"   # unsloth-2026.7.2 기준 요구 버전. unsloth 업그레이드 시 재확인 필요.

Write-Host "패키지를 설치합니다..."
& $pip install --upgrade pip | Out-Null
& $pip install "torch==$torchVersion" --index-url https://download.pytorch.org/whl/cu128
if ($LASTEXITCODE -ne 0) {
    Write-Error "torch(CUDA 12.8) 설치 실패"
    exit 1
}
& $pip install unsloth unsloth_zoo bitsandbytes pyyaml datasets pillow
if ($LASTEXITCODE -eq 0) {
    $installedTorch = & (Join-Path $venvPath "Scripts\python.exe") -c "import torch; print(torch.__version__)"
    if ($installedTorch -notlike "*+cu128*") {
        Write-Error "unsloth 설치 후 torch가 CUDA 빌드에서 벗어났습니다 (현재: $installedTorch). torchVersion 변수를 unsloth가 요구하는 버전으로 갱신하세요."
        exit 1
    }
}
if ($LASTEXITCODE -ne 0) {
    Write-Error "패키지 설치 실패 (Windows 네이티브 환경에서 unsloth/bitsandbytes 빌드 문제일 수 있음 — WSL2 또는 train_pipeline/Dockerfile 사용 검토)"
    exit 1
}
# ─────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "활성화 명령:"
Write-Host "  . $venvPath\Scripts\Activate.ps1"
Write-Host ""
Write-Host "동작 확인 (GPU 필요 — unsloth는 accelerator 없이는 import 자체가 실패함):"
Write-Host "  python -c `"import torch; print(torch.__version__, torch.cuda.is_available())`""
Write-Host "  python -c `"import unsloth`""
