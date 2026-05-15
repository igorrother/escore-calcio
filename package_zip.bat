@echo off
REM Build the Windows .exe (if needed) and produce a versioned end-user ZIP
REM that can be shared via Google Drive / OneDrive / email. No installer.

setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv not found. Create it first:
    echo     python -m venv .venv
    echo     .venv\Scripts\pip install -r requirements.txt
    exit /b 1
)

if not exist "dist\EscoreCalcio\EscoreCalcio.exe" (
    echo dist\EscoreCalcio not found. Running build_windows.bat first...
    call build_windows.bat
    if errorlevel 1 exit /b 1
)

".venv\Scripts\python.exe" tools\package.py
if errorlevel 1 (
    echo [ERROR] Packaging failed.
    exit /b 1
)

endlocal
