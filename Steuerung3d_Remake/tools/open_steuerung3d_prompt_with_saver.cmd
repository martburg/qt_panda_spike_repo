@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ====== CONFIG (edit these) ======
set "ENVNAME=Steuerung3d"
set "REPO=C:\Users\MartinDev\dev\Steuerung3d_Remake"

REM Truth vault (GitHub-synced Obsidian)
set "VAULT=C:\Users\MartinDev\Documents\obsidian"

REM Saver script stays in the code repo tools folder
set "SERVER_PY=%REPO%\tools\chatgpt_active_to_obsidian.py"

set "HOST=127.0.0.1"
set "PORT=8765"
set "PING_URL=http://%HOST%:%PORT%/ping"

REM These are in the TRUTH vault (because server will write there)
set "LOCKFILE=%VAULT%\Logs\server.lock"
set "LOGFILE=%VAULT%\Logs\server.log"
REM =================================

REM --- Ensure curl exists (Win11 should have it) ---
where curl.exe >nul 2>nul
if errorlevel 1 (
  echo ERROR: curl.exe not found on PATH.
  goto :keep_prompt
)

REM --- Initialize conda (miniconda) ---
set "CONDA_ACT=%USERPROFILE%\miniconda3\Scripts\activate.bat"
if not exist "%CONDA_ACT%" (
  echo ERROR: conda activate not found at "%CONDA_ACT%"
  goto :keep_prompt
)

call "%CONDA_ACT%" "%USERPROFILE%\miniconda3" >nul 2>nul
call conda activate "%ENVNAME%"
if errorlevel 1 (
  echo ERROR: Failed to activate conda env "%ENVNAME%"
  goto :keep_prompt
)

REM Get env python path for launching the server in a separate window
set "PYEXE=%CONDA_PREFIX%\python.exe"
if not exist "%PYEXE%" (
  echo ERROR: Python not found at "%PYEXE%"
  goto :keep_prompt
)

REM --- Check if server already running ---
call :ping_ok
if not errorlevel 1 (
  echo Obsidian saver already running: %PING_URL%
  goto :ready
)

REM --- Not running: start it ---
echo Obsidian saver not running. Starting...

if not exist "%SERVER_PY%" (
  echo ERROR: Server script not found: "%SERVER_PY%"
  goto :keep_prompt
)

REM If a stale lock exists, remove it before starting
REM (safe because we already verified server is NOT reachable)
if exist "%LOCKFILE%" (
  del "%LOCKFILE%" >nul 2>nul
)

REM Start server in a separate minimized window using the env's python
REM and override VAULT_DIR via environment variable.
start "ObsidianSaver" /MIN cmd /c ^
  "set OBSIDIAN_VAULT_DIR=%VAULT%&& "%PYEXE%" "%SERVER_PY%""

REM Wait until it answers /ping (up to ~40 seconds)
for /l %%i in (1,1,40) do (
  call :ping_ok
  if not errorlevel 1 goto :ready
  timeout /t 1 /nobreak >nul
)

echo ERROR: Server did not come up on %PING_URL%
echo Check: "%LOGFILE%"
goto :keep_prompt

:ready
cd /d "%REPO%"
echo.
echo ==========================================
echo Steuerung3d dev prompt ready
echo - Conda env : %CONDA_DEFAULT_ENV%
echo - Saver URL : %PING_URL%
echo - Code repo : %REPO%
echo - Vault     : %VAULT%
echo - Log       : %LOGFILE%
echo ==========================================
echo.
cmd /k
goto :eof

:keep_prompt
echo.
echo Keeping prompt open for debugging...
cmd /k
goto :eof

REM --- Helper: ping server quickly (reliable exit code) ---
:ping_ok
curl.exe -s -S --max-time 1 "%PING_URL%" >nul 2>nul
exit /b %ERRORLEVEL%
