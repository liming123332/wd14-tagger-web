@echo off
chcp 65001 >nul
title 翻译 GPU 加载诊断
cd /d "%~dp0"
echo 正在诊断（输出存到文件，防止崩溃丢失）...
runtime\python.exe -u "%~dp0diag_llama_gpu.py" > "%~dp0diag_gpu_output.txt" 2>&1
type "%~dp0diag_gpu_output.txt"
echo.
echo ========================================
echo 诊断完成，结果已存到 diag_gpu_output.txt（与本 .bat 同目录）
echo 请把这个文件【diag_gpu_output.txt】发回给作者
echo ========================================
pause
