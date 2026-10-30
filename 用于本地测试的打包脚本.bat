@echo OFF
chcp 65001 >nul
setlocal
cd /d "%~dp0"

:: ============================================================
:: Local build script (no Anaconda required)
:: Put this file in the project root, next to src\
:: ============================================================

set "VENV_DIR=.venv"
set "APP_NAME=wvd"
set "USE_CONSOLE=1"
set "PYTHON_CMD=py -3.10"

echo ============================================================
echo   Local Build Script
echo   Project root : %CD%
echo   Python       : %PYTHON_CMD%
echo   Venv         : %VENV_DIR%
echo   App          : %APP_NAME%
echo   Console      : %USE_CONSOLE%
echo ============================================================
echo.

%PYTHON_CMD% --version
if errorlevel 1 (
    echo [ERROR] Failed to run %PYTHON_CMD%
    pause
    exit /b 1
)

:: ---------- Create venv ----------
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [INFO] Creating virtual environment...
    %PYTHON_CMD% -m venv %VENV_DIR%
    if errorlevel 1 (
        echo [ERROR] Failed to create venv.
        pause
        exit /b 1
    )
)

:: ---------- Activate venv ----------
echo [INFO] Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"
if not defined VIRTUAL_ENV (
    echo [ERROR] Failed to activate venv.
    pause
    exit /b 1
)
echo       VIRTUAL_ENV = %VIRTUAL_ENV%
python --version
echo.

:: ---------- Install dependencies ----------
echo [INFO] Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

:: ---------- Compile Babel ----------
if exist "locale" (
    echo [INFO] Compiling translation catalogs...
    python -m babel.messages.frontend compile -d locale -D messages
    if errorlevel 1 (
        echo [ERROR] Babel compile failed.
        pause
        exit /b 1
    )
)

:: ---------- Clean previous build ----------
echo [INFO] Cleaning previous build...
rd /s /q "dist"  2>nul
rd /s /q "build" 2>nul
del /q "%APP_NAME%.spec" 2>nul

:: ---------- Flags ----------
set "CONSOLE_FLAG=--console"
if "%USE_CONSOLE%"=="0" set "CONSOLE_FLAG=--noconsole"

:: ---------- Build ----------
echo.
echo [INFO] Running PyInstaller...
echo.
pyinstaller %CONSOLE_FLAG% --onedir ^
    --paths=src ^
    --collect-submodules=ppadb ^
    --add-data "resources;resources/" ^
    --add-data "locale;locale/" ^
    src/main.py -n %APP_NAME%
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo [INFO] Build finished.
echo   exe : dist\%APP_NAME%\%APP_NAME%.exe
echo.
echo   If it crashes, run it manually in CMD to see errors.
echo ============================================================

explorer "dist\%APP_NAME%"

pause
endlocal