# WD14 反推标注 Web 系统

本地运行的图片反推标注工具：WD14 反推 → 自动归类 → 提示词翻译 → 本地持久化 → 网页查看编辑。全本地运行，图片与模型不外传。

## 核心功能

- **WD14 反推**：多模型反推（JoyTag / WD14 等），输出标签并自动 6 类归类（人数 / 发型 / 服饰 / 场景 / 构图 / 画质）。
- **提示词翻译（本地 Hy-MT2）**：
  - **英 → 中**：各分类标签原位显示中文释义，看一眼就懂标签含义。
  - **中 → 英**：详情页添加标签时输入中文，自动翻译成英文标签加入。
- **本地持久化**：图片 + 标签 + 分类 + 收藏全部本地存储，图库浏览、详情编辑、批量操作。
- **便携包**：一键打包 Windows 免安装整合包（Python 运行时 + 模型 + 前端构建产物）。

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

## 提示词翻译

翻译基于腾讯 **Hy-MT2-1.8B** 多语言翻译模型，通过 `llama-cpp-python` 在 GPU 上进程内推理，**不联网、不落地**——每次请求现译，结果不写库。

### 模型选型

| 选项 | 说明 |
|------|------|
| **unsloth Q4_K_M（采用）** | 标准 K-quant，1.13GB，1.8B 上近乎无损，标准 llama.cpp 即可加载 |
| 原版腾讯 GGUF | 依赖腾讯自定义 STQ kernel（未并入 llama.cpp 主线，标准 wheel 无法加载），弃用 |
| IQ2_M（2-bit） | 体积小但高频词（solo / pleated_skirt / 1girl）语义丢失严重，弃用 |

模型下载到 `models/hy_mt2_2bit/Hy-MT2-1.8B-Q4_K_M.gguf`（目录名沿用历史命名，实际为 Q4_K_M）。

### 词典兜底

通用翻译模型对 danbooru 专有标签有盲区（`solo`→「仅限」、`1girl`→「1 名女」）。内置 `backend/translate/danbooru_glossary.json`（252 条高频标签中英对照）做后处理兜底，可自行扩充：

- **英 → 中**：命中词典直接用权威译名、跳过模型推理（更快更准）；未命中再走 Hy-MT2。
- **中 → 英**：反向查词典（「双马尾」→ `twintails`、「水手服」→ `serafuku`、「单人」→ `solo`）；未命中走模型译成英文短语。

### 用法

- **看标签释义**：详情页任意分类点「翻译本分类」，标签下方原位显示中文小字。
- **中文添加标签**：分类的添加标签框输入中文（如「双马尾」或「双马尾，百褶裙，过膝袜」），回车自动翻译成英文标签批量加入；输入纯英文 / 下划线标签则直接加入。
- **不带下划线**：翻译得到的标签以空格分隔短语保存与显示（`cat ears`、`pleated skirt`），不保留下划线；WD14 反推与权威标签在显示层同样渲染为空格。
- **下载 / 卸载**：设置页下载翻译模型（约 1.1GB）；不用时可卸载释放显存（GGUF 文件保留，下次自动重新加载）。

### 相关接口

- `GET  /api/translate/status` — 模型是否已下载 / 已加载
- `POST /api/translate/download` — 下载并加载模型
- `POST /api/translate` — 批量翻译（英 → 中，默认）
- `POST /api/translate/to-tags` — 中文 → 英文标签短语（中 → 英）
- `POST /api/translate/unload` — 卸载模型释放显存

## 便携包打包

```bash
python pack_portable.py
```

打包 Windows 免安装整合包：内置嵌入式 Python 运行时、依赖、WD14 模型与前端构建产物。

> 翻译推理依赖 `llama-cpp-python` 的 Blackwell CUDA 预编译 wheel（PyPI / 清华源均无 Windows 预编译包，本机无 MSVC 会编译失败）。需将 wheel 放到 `_dl/` 目录，打包脚本会自动识别安装（`llama_cpp_python*.whl`）；缺失时仅警告，翻译功能不可用但不影响 tagger 主流程。

## 目录结构

```
wd14-tagger-web/
├── backend/
│   ├── api/            # FastAPI 路由（图片/角色/画师/提示词/翻译...）
│   ├── tagger/         # WD14 反推（ONNX Runtime GPU）
│   ├── translate/      # Hy-MT2 翻译（llama-cpp-python GGUF）
│   │   ├── translator.py
│   │   └── danbooru_glossary.json   # 252 条标签中英对照词典
│   └── storage/        # 本地持久化
├── frontend/           # Vue3 + naive-ui 前端
├── models/             # 模型文件（wd14/、hy_mt2_2bit/）
├── pack_portable.py    # 便携包打包脚本
├── start.bat / dev.bat # 一键启动
└── requirements.txt
```
