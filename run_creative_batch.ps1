<#
.SYNOPSIS
    tech_electronics / entertainment / fashion_apparel / food_beverage 영상들을
    30분 간격으로 creative 추출 + 벡터 적재(run_batch.py --module evaluation
    --mode creative --extract --load_vector) 백그라운드 실행.

.DESCRIPTION
    run_batch.py 를 재사용해 video_id 목록을 --interval 초 간격으로 순차 실행한다.
    Start-Process -WindowStyle Hidden 으로 띄우므로 콘솔을 닫아도 계속 동작한다.

.EXAMPLE
    # 기본값(33편, 30분 간격, output/total 데이터)으로 실행
    .\run_creative_batch.ps1

.EXAMPLE
    # 데이터 루트나 간격을 바꿔서 실행
    .\run_creative_batch.ps1 -DataDir "D:\other_output\total" -IntervalSeconds 600
#>

param(
    [string]$DataDir        = "C:\Analysis_workspace\ad_video_analysis\output\total",
    [string]$VideoIds       = "57,78,119,205,361,498,419,420,421,416,458,468,147,246,366,199,273,276,226,217,198,300,281,430,138,109,384,98,111,52,264,471",
    [int]   $IntervalSeconds = 1800,
    [string]$RepoRoot       = "C:\Analysis_workspace\ad_video_analysis\ad_video_analysis",
    [string]$PythonExe      = "C:\Analysis_workspace\ad_video_analysis\.venv\Scripts\python.exe",
    [string]$LogDir         = "C:\Analysis_workspace\ad_video_analysis\ad_video_analysis\output"
)

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"   # 파일 리다이렉트 시 stdout 블록버퍼링을 끄고 즉시 flush (로그 실시간성)

if (-not (Test-Path $DataDir)) {
    throw "DataDir 가 존재하지 않음: $DataDir"
}
if (-not (Test-Path $PythonExe)) {
    throw "PythonExe 가 존재하지 않음: $PythonExe"
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$logOut = Join-Path $LogDir "creative_batch_out.log"
$logErr = Join-Path $LogDir "creative_batch_err.log"

$argList = @(
    "run_batch.py",
    "--video_ids", $VideoIds,
    "--module", "evaluation",
    "--interval", "$IntervalSeconds",
    "--", "--mode", "creative", "--extract", "--load_vector", "--data_dir", $DataDir
)

$proc = Start-Process -FilePath $PythonExe `
    -ArgumentList $argList `
    -WorkingDirectory $RepoRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $logOut `
    -RedirectStandardError $logErr `
    -PassThru

Write-Host "백그라운드 시작됨 (PID=$($proc.Id))"
Write-Host "  data_dir : $DataDir"
Write-Host "  video_ids: $VideoIds"
Write-Host "  interval : ${IntervalSeconds}초"
Write-Host "  로그(표준출력): $logOut"
Write-Host "  로그(표준에러): $logErr"
Write-Host ""
Write-Host "진행 확인: Get-Content `"$logOut`" -Tail 30 -Wait"
Write-Host "중단     : Stop-Process -Id $($proc.Id)"
