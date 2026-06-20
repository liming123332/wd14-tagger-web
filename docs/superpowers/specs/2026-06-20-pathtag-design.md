# 路径打标（PathTag）功能设计

- 日期：2026-06-20
- 状态：待评审
- 目标项目：`wd14-tagger-web`

## 1. 目标

新增一个前端页签「路径打标」：用户输入一个**本地文件夹路径**，后端读取该路径下的所有图片，调用反推模型生成标签，并把结果写成**与图片同名、同目录的 `.txt`**（如 `a.png` → `a.txt`）。

支持模型选择（wd14 / cl_tagger / cl_tagger_v2），默认 `cl_tagger_v2`。

## 2. 背景与复用决策（mikazuki 评估）

参考实现 `I:\trae\wd14\mikazuki` 评估结论：

- **不 import mikazuki**：它不是独立可 import 的 Python 包（无 pyproject / setup.py），且依赖 `torch` + `cv2` + `pandas`，与本项目的轻量后端（`onnxruntime + numpy + PIL`）冲突。
- **mikazuki 没有 cl_tagger_v2**：其 `available_interrogators` 只有 `cl_tagger_1_01`。本项目已有完整的 `backend/tagger/cl_tagger_v2.py`，无需借它的推理实现。
- **推理 + 后处理本项目已具备**：`get_tagger(model).tag_image()` 返回 `{tag: score}`，阈值过滤与 `_`→空格在 tagger 层已完成。
- **仅借鉴 mikazuki 的胶水逻辑**（照搬改写，不引入依赖）：
  - 文件夹路径 → glob 展开成图片列表（含扩展名过滤、递归）—— `mikazuki/tagger/interrogator.py:134-163`
  - 标签 → 逗号文本 → 写同名 `.txt` —— `mikazuki/tagger/interrogator.py:196-242`

## 3. 架构总览

纯新增一层「路径读图 → 反推 → 写 txt」的胶水，**不碰 storage / meta / Classifier**（用户决策：纯写 txt、不入库、纯逗号无权重）。

```
前端 PathTagPage
  │  startPathTag({path, model, th, recursive, on_conflict})
  ▼
POST /api/pathtag/start  ──→  expand_images(path) 校验+展开  ──→  {job_id, total}
  │
  │  EventSource: GET /api/pathtag/{job_id}/events
  ▼
pathtag task runner (asyncio)
  for 每张图:
    Image.open(path)
    get_tagger(model).tag_image(pil, gen_th, char_th, use_char)  → {tag:score}
    text = ', '.join(按 score 降序的 tags)
    path.with_suffix('.txt').write_text(text)   (overwrite | skip)
    推 SSE: progress / error
  推 SSE: done
```

执行方式：**异步任务 + SSE 进度**（复用 `backend/tasks/queue.py` 的成熟模式）。大批量（数百上千张）不阻塞、有实时进度，与现有 batch 体验一致。

## 4. 后端设计

### 4.1 API 契约

**`POST /api/pathtag/start`**

请求体（JSON）：
```json
{
  "path": "I:/some/folder",
  "model": "cl_tagger_v2",
  "gen_th": 0.55,
  "char_th": 0.55,
  "use_char": true,
  "recursive": false,
  "on_conflict": "overwrite"
}
```
- `model`：必须是 `MODEL_SPECS` 中的 key，否则 400。
- `on_conflict`：`"overwrite"` | `"skip"`，默认 `"overwrite"`。
- `recursive`：默认 `false`。
- `use_char` / `char_th`：对 `cl_tagger_v2` 无实际作用（v2 单阈值），仅为接口一致性保留（与 `tag_image` 签名对齐）。

校验：`Path(path).is_dir()` 为假 → 400 `path not found or not a directory`。

响应：
```json
{ "job_id": "ph_xxx", "total": 42 }
```
`job_id` 由后端生成（如 `ph_` + 短随机/uuid）；`total` 为展开后的图片数。空目录也允许启动（total=0，runner 直接推 done）。

**`GET /api/pathtag/{job_id}/events`**（SSE，`text/event-stream`）

事件结构与现有 batch events 对齐：
- `progress`：`{ "type": "progress", "done": N, "total": M, "current": "a.png", "status": "ok" | "skip" }`
- `error`：`{ "type": "error", "current": "b.png", "message": "..." }`
- `done`：`{ "type": "done", "done": N, "total": M, "errors": K }`（errors = 失败张数）

job 不存在 → 404。

### 4.2 task runner —— `backend/tasks/pathtag.py`

结构参考 `backend/tasks/queue.py`，但输入（文件系统路径）与输出（写 txt、不入库）不同，**独立实现、不耦合**。

- 任务状态：内存 `dict[job_id → PathTagState]`，`PathTagState` 含 `total / done / errors / events: list / is_done: bool`（参考现有 batch 的 state 结构）。
- 启动：`POST /start` 中同步展开图片列表（`expand_images`，见 4.3），建 state，用 `asyncio`（或现有 batch 用的并发原语）起后台任务，立即返回 `{job_id, total}`。
- 主循环（推理用 `asyncio.to_thread` 包裹，避免阻塞事件循环，与 queue.py 一致）：
  ```
  for p in images:
      try:
          with Image.open(p) as pil:
              tags = get_tagger(model).tag_image(pil, gen_th, char_th, use_char)
          text = ', '.join(sorted(tags, key=tags.get, reverse=True))
          out = p.with_suffix('.txt')
          if on_conflict == 'skip' and out.exists():
              推 progress(status='skip'); continue
          out.write_text(text, encoding='utf-8')
          推 progress(status='ok')
      except (UnidentifiedImageError, OSError) as e:
          推 error(current=p.name, message=str(e))   # 单张失败不中断整批
  推 done(done, total, errors)
  ```
- `get_tagger(model)` 复用现有 lazy-load 缓存（首次推理触发加载，与单图/批量反推一致）。

### 4.3 `expand_images(path, recursive) -> list[Path]`

照搬 mikazuki `interrogator.py:134-163` 的思路：
- glob 模式：`path/*`；`recursive=True` 时 `path/**/*`（配合 `glob(..., recursive=True)`）。
- 扩展名过滤：用 `PIL.Image.registered_extensions()` 中 `Image.OPEN` 支持的扩展名集合（与 mikazuki 一致，覆盖 png/jpg/jpeg/webp/bmp 等）。
- 结果排序：按文件名排序，保证进度展示稳定可预测。

### 4.4 文本生成

`tag_image()` 返回 `{tag: score}`（已过阈值、已替换 `_`→空格），因此：
```
text = ', '.join(sorted(tags.keys(), key=lambda t: tags[t], reverse=True))
```
按分数降序、纯逗号分隔、无权重。**不走 Classifier**（用户决策：纯逗号，不需要分桶）。

### 4.5 路由注册

在 `backend/main.py` 中 `include_router(routes_pathtag.router)`。

## 5. 前端设计

### 5.1 路由 + 导航

- `frontend/src/router.ts`：加 `{ path: '/pathtag', component: PathTagPage }`。
- `frontend/src/App.vue` 的 `ITEMS` 数组：加 `{ label: '路径打标', key: '/pathtag', icon: <新图标> }`。

### 5.2 `frontend/src/views/PathTagPage.vue`

布局参考 `UploadPage.vue`（NCard + 设置项 + 操作区）：
- **路径输入**：`n-input`（输入文件夹绝对路径）。
- **模型选择**：复用 `useTagger`（`state.taggers` 下拉 + 下载检测 + 未下载时提示下载）。
- **阈值滑块**：`gen_th` / `char_th`（复用 UploadPage 的模型切换 `watch`，按模型调默认阈值：v2→0.55/0.55，cl_tagger→0.35/0.6，wd14→0.35/0.9）。
- **选项**：「包含子文件夹」checkbox（recursive）；「同名 txt 已存在」select（overwrite / skip）。
- **开始按钮**：调 `usePathTag().start()`；进行中禁用。
- **进度区**：复用 `BatchBars`（或进度条 + 当前文件名 + done/total + 错误列表），由 SSE 事件驱动。

### 5.3 `frontend/src/composables/usePathTag.ts`

参考 `useBatch` 的结构：管理 job 状态（idle / running / done、done/total/errors、当前文件、错误列表）+ SSE 订阅（启动时 `new EventSource(subscribePathTag(jobId))`，按事件更新状态，`done` 或断开时关闭）。

### 5.4 `frontend/src/api/client.ts`

新增（参考现有 `startBatch` / `subscribeBatch`）：
- `startPathTag(payload): Promise<{ job_id, total }>` —— `POST /api/pathtag/start`。
- `subscribePathTag(jobId): string` —— 返回 SSE URL（供 `EventSource` 使用），与 `subscribeBatch` 返回形式一致。

## 6. 默认行为

| 项 | 默认 | 依据 |
|---|---|---|
| 递归子目录 | 否（UI 有「包含子文件夹」开关） | 单层最常见；递归作为可选 |
| 已有同名 txt | 覆盖（可选「跳过」） | 重新打标预期；提供 skip 防误删手写 |
| 图片格式 | PIL `registered_extensions()` 全支持 | 对齐 mikazuki |
| 阈值默认 | v2→0.55/0.55，cl_tagger→0.35/0.6，wd14→0.35/0.9 | 对齐 UploadPage 的 watch 逻辑 |
| 路径安全 | 仅校验 `is_dir()`，不做根目录白名单 | 本地单用户工具，非多租户 |

## 7. 错误处理

- 路径不存在 / 非目录 → 400 `path not found or not a directory`。
- `model` 不在 `MODEL_SPECS` → 400 `unknown tagger`。
- 模型未下载 → 前端开始按钮禁用并提示下载（复用 `useTagger.isDownloaded`）。
- 单张图打不开（`UnidentifiedImageError`）/ 写 txt 失败（`OSError`）→ 记 `error` 事件，**跳过该张、继续整批**（对齐 batch 容错）。
- SSE 断连 → 前端展示「连接中断」，可重新发起任务。

## 8. 测试策略

**后端**（pytest，参考 `test_deps.py` 风格，用 fake tagger mock `get_tagger`/`tag_image`）：
- `expand_images`：递归 / 非递归 / 扩展名过滤（含非图片文件被排除）。
- 文本生成：按分数降序、纯逗号、无权重。
- 写 txt：`overwrite` 覆盖已有、`skip` 跳过已有。
- 容错：单张 `Image.open` 失败不中断整批、错误计入 errors。
- `/start` 校验：非法路径 / 未知 model 返回 400。

**前端**（vitest，参考 `client.test.ts` / `UploadPage.test.ts`）：
- `client.ts` 新函数：`startPathTag` 请求体/响应、`subscribePathTag` URL 形式。
- `PathTagPage`：渲染路径输入/模型选择/选项；进行中按钮禁用；未下载模型禁用开始。

## 9. 不做（YAGNI）

- 不入图库（不写 storage / meta）。
- 不带权重格式（`(tag:score)`）。
- 不走 Classifier 分桶。
- 冲突只支持 overwrite / skip（不做 prepend / append / copy）。
- 不做文件名占位符 `[name] / [hash] / [extension]`（直接同名 `.txt`）。
- 不做根目录白名单 / 路径穿越防护（本地工具）。
- 不 import mikazuki（只借鉴 glob + 写 txt 两段逻辑，照搬改写）。

## 10. 关键文件清单

**新增**：
- `backend/api/routes_pathtag.py`
- `backend/tasks/pathtag.py`
- `frontend/src/views/PathTagPage.vue`
- `frontend/src/composables/usePathTag.ts`
- 后端测试、前端测试文件

**修改**：
- `backend/main.py`（include_router）
- `frontend/src/router.ts`（路由）
- `frontend/src/App.vue`（ITEMS 导航项）
- `frontend/src/api/client.ts`（startPathTag / subscribePathTag）
