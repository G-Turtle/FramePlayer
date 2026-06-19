# Frame Player 릴리스 빌드 자동화 (빌드까지만 — 업로드는 수동)
#
# 사용법:  ./release.ps1 0.1.1
#   1) src\version.py 와 installer\FramePlayer.iss 의 버전을 동기화
#   2) PyInstaller 폴더 빌드
#   3) Inno Setup 설치 파일 컴파일
#   결과: dist\FramePlayer-Setup-<버전>.exe
#
# 이후 GitHub Releases에 setup 파일 업로드 + 패치 내역 작성은 직접 진행한다.

param(
    [Parameter(Mandatory = $true)]
    [string]$Version
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

# --- 0. 버전 형식 검증 (X.Y.Z) ---
if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    Write-Error "버전 형식이 올바르지 않습니다. X.Y.Z 형태로 입력하세요. (예: 0.1.1)"
    exit 1
}

# UTF-8 (BOM 없음)으로 기록하여 한글 주석/인코딩을 보존한다
$utf8NoBom = New-Object System.Text.UTF8Encoding $false

function Set-VersionInFile($path, $pattern, $replacement) {
    if (-not (Test-Path $path)) { Write-Error "파일을 찾을 수 없습니다: $path"; exit 1 }
    $content = [System.IO.File]::ReadAllText($path)
    if ($content -notmatch $pattern) {
        Write-Error "버전 문자열을 찾지 못했습니다: $path"
        exit 1
    }
    $content = [regex]::Replace($content, $pattern, $replacement)
    [System.IO.File]::WriteAllText($path, $content, $utf8NoBom)
}

Write-Host "[1/3] 버전 동기화 -> $Version" -ForegroundColor Cyan
Set-VersionInFile (Join-Path $root "src\version.py") `
    '__version__\s*=\s*"[^"]*"' "__version__ = `"$Version`""
Set-VersionInFile (Join-Path $root "installer\FramePlayer.iss") `
    '#define AppVersion "[^"]*"' "#define AppVersion `"$Version`""

# --- 2. PyInstaller 빌드 ---
Write-Host "[2/3] PyInstaller 빌드..." -ForegroundColor Cyan
$pyinstaller = Join-Path $root ".venv\Scripts\pyinstaller.exe"
if (-not (Test-Path $pyinstaller)) { Write-Error "pyinstaller를 찾을 수 없습니다: $pyinstaller"; exit 1 }
& $pyinstaller --noconfirm --clean (Join-Path $root "FramePlayer.spec")
if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller 빌드 실패"; exit 1 }

# --- 3. Inno Setup 컴파일 ---
Write-Host "[3/3] Inno Setup 설치 파일 컴파일..." -ForegroundColor Cyan
$isccCandidates = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { Write-Error "ISCC.exe(Inno Setup)를 찾을 수 없습니다."; exit 1 }
& $iscc (Join-Path $root "installer\FramePlayer.iss")
if ($LASTEXITCODE -ne 0) { Write-Error "Inno Setup 컴파일 실패"; exit 1 }

$setup = Join-Path $root "dist\FramePlayer-Setup-$Version.exe"
Write-Host "`n완료!" -ForegroundColor Green
Write-Host "  설치 파일: $setup" -ForegroundColor Green
Write-Host "`n다음 단계(수동):" -ForegroundColor Yellow
Write-Host "  1) version.py / FramePlayer.iss 변경분 커밋 & 푸시" -ForegroundColor Yellow
Write-Host "  2) GitHub Releases에서 태그 v$Version 생성 + 위 setup 파일 업로드 + 패치 내역 작성" -ForegroundColor Yellow
