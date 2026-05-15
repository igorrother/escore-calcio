@echo off
REM Build the Windows .exe bundle for the Agatston calcium-score app.
REM Run from the project root after running `.venv\Scripts\pip install -r requirements.txt`.

setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\pyinstaller.exe" (
    echo [ERROR] .venv not found. Create it first:
    echo     python -m venv .venv
    echo     .venv\Scripts\pip install -r requirements.txt
    exit /b 1
)

echo Cleaning previous build...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

echo Running PyInstaller...
".venv\Scripts\pyinstaller.exe" --noconfirm score_app.spec
if errorlevel 1 (
    echo [ERROR] PyInstaller failed.
    exit /b 1
)

REM Remove the intermediate build/ folder. It contains a same-named exe that
REM looks tempting but is just the bootloader stub — launching it triggers
REM "Failed to load Python DLL '...build\score_app\_internal\python312.dll'"
REM because the runtime is in dist\, not build\.
if exist build rmdir /s /q build

echo.
echo ==============================================================
echo Build complete. The application is here:
echo.
echo     %CD%\dist\EscoreCalcio\EscoreCalcio.exe
echo.
echo Distribute the entire "dist\EscoreCalcio" folder — the exe needs
echo the _internal subfolder next to it.
echo ==============================================================
endlocal
