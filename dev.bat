@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ===== WD14 Tagger Web（开发模式 / 热更新）=====
echo 前端 dev: http://localhost:5173  （改前端代码自动刷新）
echo 后端 api: http://localhost:8000  （vite 已代理 /api 到此）
echo ================================================
echo.

if not exist ".venv\Scripts\activate.bat" (
    echo [错误] 未找到 .venv，请先按 README 安装后端依赖。
    pause & exit /b 1
)
if not exist "frontend\node_modules" (
    echo [错误] 未找到 frontend\node_modules，请先在 frontend 下执行 npm install。
    pause & exit /b 1
)

start "WD14-Backend (8000)" cmd /k "call .venv\Scripts\activate.bat && python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000"
start "WD14-Frontend (5173)" cmd /k "cd frontend && npm run dev"

echo 已启动两个窗口，关闭对应窗口即停止该服务。
