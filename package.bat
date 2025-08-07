@echo OFF
setlocal

:: 清理旧文件
echo [INFO] deleteing old data...
rd /s /q "dist" 2>nul
rd /s /q "build" 2>nul

echo Installing requirements...
pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install requirements.
    pause
    exit /b 1
)

:: 生成时间戳（格式：年月日时分）
for /f %%i in ('powershell -Command "Get-Date -Format 'yyyyMMddHHmm'"') do set timestamp=%%i

:: 打包并添加时间戳到文件名
:: pyinstaller --onefile --noconsole --add-data "resources;resources/" src/main.py -n wvd
pyinstaller --onedir --add-data "resources;resources/" src/main.py -n wvd
cp ./CHANGES_LOG.md ./dist/wvd/CHANGES_LOG.md

if errorlevel 1 (
    echo Failed to run pyinstaller.
    pause
    exit /b 1
)

echo Script finished.
pause
endlocal 