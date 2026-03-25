@echo off
REM Test Sync from Parent Repository
REM This script tests syncing from pkinyanjui461-dev/seepo to your local repo

setlocal enabledelayedexpansion

REM Read PARENT_PAT from menu.conf
for /f "tokens=2 delims==" %%A in ('findstr "PARENT_PAT=" menu.conf 2^>nul') do set "PARENT_PAT=%%A"

if "!PARENT_PAT!"=="" (
    echo [ERROR] PARENT_PAT not found in menu.conf
    echo Please run menu.exe first to set up credentials
    pause
    exit /b 1
)

echo.
echo === TESTING SYNC FROM PARENT ===
echo.
echo PARENT_PAT loaded: !PARENT_PAT!
echo.
echo Testing: git fetch from parent repository...
echo.

REM Test sync MAIN branch
echo [1] Testing MAIN branch sync...
git fetch "https://!PARENT_PAT!@github.com/pkinyanjui461-dev/seepo.git" main
if errorlevel 1 (
    echo [ERROR] Failed to fetch MAIN branch
    pause
    exit /b 1
)
echo [SUCCESS] MAIN branch fetched
echo.

REM Test sync MASTER branch
echo [2] Testing MASTER branch sync...
git fetch "https://!PARENT_PAT!@github.com/pkinyanjui461-dev/seepo.git" master
if errorlevel 1 (
    echo [ERROR] Failed to fetch MASTER branch
    pause
    exit /b 1
)
echo [SUCCESS] MASTER branch fetched
echo.

echo === ALL TESTS PASSED ===
echo.
echo Now you can run this command to sync MAIN:
echo git fetch "https://!PARENT_PAT!@github.com/pkinyanjui461-dev/seepo.git" main ^&^& git merge FETCH_HEAD --quiet
echo.
echo Or this to sync MASTER:
echo git fetch "https://!PARENT_PAT!@github.com/pkinyanjui461-dev/seepo.git" master ^&^& git merge FETCH_HEAD --quiet
echo.
pause
# Test change for push verification
