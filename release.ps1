# Frame Player 릴리스 빌드 자동화 (빌드까지만 — 업로드는 수동)
#
# 사용법:  ./release.ps1 0.1.1   또는  release.bat 더블클릭
#   1) src\version.py 와 installer\FramePlayer.iss 의 버전을 동기화
#   2) PyInstaller 폴더 빌드
#   3) Inno Setup 설치 파일 컴파일
#   결과: dist\FramePlayer-Setup-<버전>.exe
#
# 콘솔 출력은 인코딩 문제를 피하려고 영어로 둔다 (한글은 주석에만).

param(
    [Parameter(Mandatory = $true)]
    [string]$Version
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

# --- 0. 버전 형식 검증 (X.Y.Z) ---
if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    Write-Error "Invalid version format. Use X.Y.Z (e.g. 0.1.1)."
    exit 1
}

# UTF-8 (BOM 없음)으로 기록하여 한글 주석/인코딩을 보존한다
$utf8NoBom = New-Object System.Text.UTF8Encoding $false

function Set-VersionInFile($path, $pattern, $replacement) {
    if (-not (Test-Path $path)) { Write-Error "File not found: $path"; exit 1 }
    $content = [System.IO.File]::ReadAllText($path)
    if ($content -notmatch $pattern) {
        Write-Error "Version string not found in: $path"
        exit 1
    }
    $content = [regex]::Replace($content, $pattern, $replacement)
    [System.IO.File]::WriteAllText($path, $content, $utf8NoBom)
}

Write-Host "[1/3] Sync version -> $Version" -ForegroundColor Cyan
Set-VersionInFile (Join-Path $root "src\version.py") `
    '__version__\s*=\s*"[^"]*"' "__version__ = `"$Version`""
Set-VersionInFile (Join-Path $root "installer\FramePlayer.iss") `
    '#define AppVersion "[^"]*"' "#define AppVersion `"$Version`""

# --- 2. PyInstaller 빌드 ---
Write-Host "[2/3] PyInstaller build..." -ForegroundColor Cyan
$pyinstaller = Join-Path $root ".venv\Scripts\pyinstaller.exe"
if (-not (Test-Path $pyinstaller)) { Write-Error "pyinstaller not found: $pyinstaller"; exit 1 }
& $pyinstaller --noconfirm --clean (Join-Path $root "FramePlayer.spec")
if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller build failed"; exit 1 }

# --- 3. Inno Setup 컴파일 ---
Write-Host "[3/3] Inno Setup compile..." -ForegroundColor Cyan
$isccCandidates = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { Write-Error "ISCC.exe (Inno Setup) not found."; exit 1 }
& $iscc (Join-Path $root "installer\FramePlayer.iss")
if ($LASTEXITCODE -ne 0) { Write-Error "Inno Setup compile failed"; exit 1 }

$setup = Join-Path $root "dist\FramePlayer-Setup-$Version.exe"
Write-Host "`nDONE!" -ForegroundColor Green
Write-Host "  Installer: $setup" -ForegroundColor Green
Write-Host "`nNext steps (manual):" -ForegroundColor Yellow
Write-Host "  1) Commit & push changes in version.py / FramePlayer.iss" -ForegroundColor Yellow
Write-Host "  2) On GitHub Releases: create tag v$Version, upload the setup file, write patch notes" -ForegroundColor Yellow
