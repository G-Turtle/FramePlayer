# Frame Player 폴더 빌드 스크립트
# 사용법: 프로젝트 루트에서  ./build.ps1
# 결과물: dist\FramePlayer\FramePlayer.exe (+ _internal\ 에 libmpv 런타임 번들)
# 전제: 프로젝트 루트의 libs\libmpv-2.dll 이 존재해야 한다 (git 미포함, 대용량 바이너리)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$pyinstaller = Join-Path $root ".venv\Scripts\pyinstaller.exe"
$spec = Join-Path $root "FramePlayer.spec"

Write-Host "Building Frame Player (onedir)..." -ForegroundColor Cyan
& $pyinstaller --noconfirm --clean $spec

Write-Host "`nDone. Output: dist\FramePlayer\FramePlayer.exe" -ForegroundColor Green
