@echo off
title Frame Player Release Build
cd /d "%~dp0"

echo ============================================
echo   Frame Player - Release Build
echo ============================================
echo.
set /p VERSION="Enter version: "

if "%VERSION%"=="" (
    echo.
    echo [Error] No version entered. Exiting.
    echo.
    pause
    exit /b 1
)

echo.
echo Building version %VERSION% ...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0release.ps1" %VERSION%

echo.
echo ============================================
echo   Finished. Press any key to close.
echo ============================================
pause >nul
