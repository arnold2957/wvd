@echo OFF
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================================
echo   Clean Build Artifacts
echo   Project root: %CD%
echo ============================================================
echo.

echo [INFO] Removing dist\ ...
rd /s /q "dist" 2>nul

echo [INFO] Removing build\ ...
rd /s /q "build" 2>nul

echo [INFO] Removing *.spec ...
del /q "*.spec" 2>nul

echo [INFO] Removing __pycache__ folders ...
for /d /r %%D in (__pycache__) do @if exist "%%D" rd /s /q "%%D" 2>nul

echo.
echo [INFO] Done. Remaining items in project root:
dir /b
echo.
pause
endlocal