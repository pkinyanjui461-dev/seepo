@echo off
REM Setup and test git remotes for fork/upstream sync

setlocal enabledelayedexpansion

REM Read PAT and PARENT_PAT from menu.conf
for /f "tokens=2 delims==" %%A in ('findstr "PAT=" menu.conf 2^>nul') do set "PAT=%%A"
for /f "tokens=2 delims==" %%A in ('findstr "PARENT_PAT=" menu.conf 2^>nul') do set "PARENT_PAT=%%A"

if "!PAT!"=="" (
    echo [ERROR] PAT not found in menu.conf
    pause
    exit /b 1
)

if "!PARENT_PAT!"=="" (
    echo [ERROR] PARENT_PAT not found in menu.conf
    pause
    exit /b 1
)

echo.
echo === SETTING UP GIT REMOTES ===
echo.

REM Check current remotes
echo [1] Checking current remotes...
git remote -v
echo.

REM Remove old upstream if exists
echo [2] Cleaning up old remotes...
git remote remove upstream 2>nul
echo.

REM Add fork as origin
echo [3] Setting origin to fork (pgwiz/seepo)...
git remote set-url origin "https://!PAT!@github.com/pgwiz/seepo.git"
echo.

REM Add upstream (parent)
echo [4] Adding upstream (pkinyanjui461-dev/seepo)...
git remote add upstream "https://!PARENT_PAT!@github.com/pkinyanjui461-dev/seepo.git"
echo.

echo [5] Verifying remotes...
git remote -v
echo.

echo === NOW YOU CAN USE THESE COMMANDS ===
echo.
echo Sync MAIN from upstream:
echo   git fetch upstream main
echo   git merge upstream/main --quiet
echo.
echo Sync MASTER from upstream:
echo   git fetch upstream master
echo   git merge upstream/master --quiet
echo.
echo Push MAIN to upstream:
echo   git push upstream main
echo.
echo Push MASTER to upstream:
echo   git push upstream master
echo.
echo === TESTING FETCH ===
echo.
git fetch upstream main
if errorlevel 1 (
    echo [ERROR] Failed to fetch from upstream
    pause
    exit /b 1
)
echo [SUCCESS] Fetch from upstream works!
echo.
pause
