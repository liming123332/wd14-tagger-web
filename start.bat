@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ===== WD14 Tagger Web（生产模式）=====
echo 访问: http://127.0.0.1:8000
echo 提示: 改动前端后请重新构建 — cd frontend ^&^& npm run build
echo ========================================
echo.

:: ===== 可选：把数据目录外置到其他硬盘或 NAS（不配置则用本地 data\）=====
:: NAS（UNC 路径，需当前账户对该共享有读写权限）：
::   set WD14_DATA_DIR=\\Z4-eydz\135xxxx4048\wd14\data
:: 其他盘：
::   set WD14_DATA_DIR=D:\tagger-data
:: set WD14_DATA_DIR=

if not exist ".venv\Scripts\activate.bat" (
    echo [错误] 未找到 .venv，请先按 README 创建虚拟环境并安装依赖。
    pause & exit /b 1
)

call ".venv\Scripts\activate.bat"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
pause
