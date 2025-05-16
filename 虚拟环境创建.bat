@echo off
setlocal enabledelayedexpansion

:: 设置Anaconda基础环境路径
set "ANACONDA_PATH=C:\P\Anaconda"

:PROMPT
set /p INPUT=是否创建虚拟环境？(Y/N): 
if /i "!INPUT!"=="Y" (
    echo 正在创建虚拟环境...
    call "%ANACONDA_PATH%\Scripts\activate.bat" base
    mkvirtualenv vpy
    pause
    goto :END
)
if /i "!INPUT!"=="N" (
    echo 正在删除虚拟环境...
    call "%ANACONDA_PATH%\Scripts\activate.bat" base
    rmvirtualenv vpy
    pause
    goto :END
)
echo 输入无效，请重新输入
goto :PROMPT

:END
echo 操作执行完毕
pause