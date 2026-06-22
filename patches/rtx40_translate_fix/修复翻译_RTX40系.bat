@echo off
chcp 65001 >nul
title WD14 翻译修复 - RTX 40 系
cd /d "%~dp0"

echo ========================================
echo   WD14 翻译功能修复 (RTX 40 系专用)
echo ========================================
echo.

REM 1. 检测是否在整合包根目录（能看到 runtime 文件夹）
if not exist "runtime\python.exe" (
    echo [错误] 未找到 runtime\python.exe
    echo.
    echo 请把本脚本和 wheel 文件一起放到整合包根目录
    echo （就是能看到 runtime 文件夹的那一层，通常是 ...\WD14-Tagger-Web-Portable\）
    echo.
    pause
    exit /b 1
)

REM 2. 查找当前目录的 sm89 wheel
set "WHL="
for %%f in (llama_cpp_python*sm89*ada*.whl) do set "WHL=%%f"

if "%WHL%"=="" (
    echo [错误] 未找到 RTX 40 系推理库 wheel
    echo.
    echo 请把下载的：
    echo   llama_cpp_python-0.3.20+cuda13.0.sm89.ada-py3-none-win_amd64.whl
    echo 放到本脚本同一个文件夹后重试。
    echo.
    pause
    exit /b 1
)

echo 检测到推理库: %WHL%
echo.
echo [1/2] 卸载旧的 Blackwell 推理库...
runtime\python.exe -m pip uninstall -y llama_cpp_python
echo.
echo [2/2] 安装 RTX 40 系专用推理库...
runtime\python.exe -m pip install "%WHL%"
echo.

if errorlevel 1 (
    echo ========================================
    echo   [失败] 安装出错，请把上方日志截图发给作者
    echo ========================================
) else (
    echo ========================================
    echo   修复完成！
    echo   请关闭本窗口，重新双击整合包的启动脚本
    echo   然后测试翻译功能是否正常
    echo ========================================
)
echo.
pause
