@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ===== WD14 Tagger Web（生产模式）=====
echo 访问: http://127.0.0.1:8000
echo 提示: 改动前端后请重新构建 — cd frontend ^&^& npm run build
echo ========================================
echo.

if not exist ".venv\Scripts\activate.bat" (
    echo [错误] 未找到 .venv，请先按 README 创建虚拟环境并安装依赖。
    pause & exit /b 1
)

call ".venv\Scripts\activate.bat"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
pause
