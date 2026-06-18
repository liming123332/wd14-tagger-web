# WD14 反推标注 Web 系统

本地运行的图片反推标注工具：WD14 模型反推 → 6 类自动归类 → 图片与提示词本地持久化 → 网页查看与编辑。

## 快速开始

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
