# WD14 反推标注 Web 系统

本地运行的图片反推标注工具：WD14 模型反推 → 6 类自动归类 → 图片与提示词本地持久化 → 网页查看与编辑。

## 快速开始

### 一键启动脚本（Windows）

首次按下方「后端 / 前端」装好依赖后，双击即可启动：

- `start.bat` — 生产模式：单进程 uvicorn 托管已构建前端，访问 http://127.0.0.1:8000（改前端后需重新 `npm run build`）。
- `dev.bat` — 开发模式：分别启动 vite（5173，热更新）与 uvicorn（8000，`--reload`），访问 http://localhost:5173，`/api` 自动代理到 8000。

### 后端
```bash
cd wd14-tagger-web
python -m venv .venv
.venv/Scripts/activate      # Windows (Git Bash: source .venv/Scripts/activate)
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

### 前端（开发）
```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173
```

### 生产
```bash
cd frontend && npm run build && cd ..
uvicorn backend.main:app --port 8000   # 访问 http://localhost:8000
```

首次反推会自动下载 WD14 模型到 `models/wd14/`（约 400MB）。
