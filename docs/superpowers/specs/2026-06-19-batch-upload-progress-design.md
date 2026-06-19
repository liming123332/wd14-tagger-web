# 批量上传进度与跨页状态保持 — 设计文档

> 日期：2026-06-19 ｜ 适用项目：wd14-tagger-web（前端）

## 1. 背景与目标

当前上传/反推的进度状态全部存在 `UploadPage.vue` 的局部 `ref` 里（`batchId`、`total`），且 `BatchProgress.vue` 的 SSE 订阅绑定在组件上。后果：

- 切换页签（上传 → 图库 → 上传）时 `UploadPage` 卸载，**进度丢失**、EventSource 被迫断开。
- 「开始」按钮处理中**未禁用**，可重复点击触发多个并发批次。
- 没有全局可见的「还剩多少没处理」。
- 只有反推有进度，上传是一次性批量 POST，无逐张进度。

本设计新增全局状态保持、处理中禁用重复上传、批量详情页、导航栏全局进度、双进度条。

## 2. 需求

1. 处理中（上传 + 反推未完成）禁用「选择图片」和「开始」，防止重复上传。
2. 上传状态全局化：切到图库再切回，进度完整恢复。
3. 上传页内联精简进度 + 「查看详情」入口跳转批量详情页。
4. 导航栏全局显示进度，**分两段**：上传 X/Y · 反推 A/B。
5. 双进度条：上传进度条 + 反推进度条（上传改为逐张上传以获得真实进度）。

## 3. 架构决策

- **A. 模块级单例 composable `useBatch()`**（选定）。对比方案：引入 pinia（标准但 overkill、新增依赖）；`<keep-alive>` 保住 UploadPage（解决不了导航栏跨组件共享）。选定 A：零依赖、天然全局、SSE 订阅放进 store 不绑组件。
- **取舍 1-a：仅当前浏览器会话保持**。状态在内存单例，刷新 / 关页即丢，不做 `status` 轮询恢复（YAGNI）。
- **取舍 2-b：进度分两段显示**「上传 X/Y · 反推 A/B」，不合并成单一「未处理 N」。

## 4. 状态模型 — `frontend/src/composables/useBatch.ts`

模块顶层单例（所有组件 import 同一实例）：

```ts
import { reactive } from 'vue'

type Phase = 'idle' | 'uploading' | 'tagging' | 'done' | 'error'
interface Item { id: string; name: string; status: 'pending' | 'ok' | 'error'; msg?: string }

const state = reactive({
  phase: 'idle' as Phase,
  total: 0,          // 本批次总图数
  uploaded: 0,       // 已上传张数
  tagged: 0,         // 已反推完成（成功）张数
  failed: 0,         // 反推失败张数
  current: '',       // 当前处理的图名
  batchId: null as string | null,
  items: [] as Item[],
  autoTag: true, genTh: 0.35, charTh: 0.9,
})

let es: EventSource | null = null   // 由 store 持有，不绑组件

export function useBatch() {
  const isBusy = () => state.phase === 'uploading' || state.phase === 'tagging'

  async function start(files: File[], autoTag: boolean, genTh: number, charTh: number) { /* 见 §5 */ }
  function _subscribe(batchId: string) { /* 见 §5 */ }
  function reset() { state.phase = 'idle'; state.total = state.uploaded = state.tagged = state.failed = 0;
                     state.current = ''; state.batchId = null; state.items = []; es?.close(); es = null }
  return { state, isBusy, start, reset }
}
```

## 5. 数据流

`start(files, autoTag, genTh, charTh)`：

1. `reset()` → `phase='uploading'`，`total=files.length`，`items` 初始化为每张 `{id:'', name:file.name, status:'pending'}`。
2. **逐张上传**：对每个 file 调 `uploadOne(file)`：
   - 成功 → `uploaded++`，记录返回的 `id` 到 `items[i]`，`items[i].status` 暂保持 pending（待反推）。
   - 失败 → `items[i].status='error'`，`items[i].msg=错误`，**继续其余**，不中断。
3. 收集所有成功上传的 `ids`。若全部失败 → `phase='error'`，结束。
4. 若 `autoTag` 且 `ids.length`：
   - `startBatch(ids, genTh, charTh)` → 拿 `batch_id`，`state.batchId=batch_id`，`phase='tagging'`，`_subscribe(batch_id)`。
   - 否则（`autoTag=false`）→ 上传成功的 `items` 全部标 `ok`，`phase='done'`，结束。
5. `_subscribe(batchId)`：`es = new EventSource('/api/batch/<id>/events')`
   - `progress` → `tagged++`，`current=ev.current`，按 `ev.id` 把对应 `items` 标 `ok`。
   - `error` → `failed++`，按 `ev.id` 标 `error` + `ev.message`。
   - `done` → `phase='done'`，`es.close()`。

> EventSource 仅在 `start`/`_subscribe` 时创建，在 `done`/`reset` 时关闭。组件不持有 ES 引用，杜绝泄漏与切页中断。

## 6. 组件 / 文件改动清单

| 文件 | 改动 |
|---|---|
| **新增** `composables/useBatch.ts` | 如 §4/§5 的全局 store |
| `api/client.ts` | 新增 `uploadOne(file): Promise<{id,source_name}>`（单文件 POST `/api/images`）。新增 `getBatchStatus(id)` 封装（备用）。保留 `uploadImages`（向后兼容，本流程不再用） |
| `App.vue` | `NMenu` 旁挂 `<BatchBadge />` |
| **新增** `components/BatchBadge.vue` | 读 `useBatch`：`isBusy` 时显示「↑`uploaded/total` · ↓`tagged/total`」；有 `batchId` 可点击跳 `/batch/:id`；`done` 显示「完成 total」后淡出；`idle` 不显示 |
| `views/UploadPage.vue` | 改用 `useBatch`；「选择」「开始」`disabled=isBusy`；内联两条 `n-progress`（上传 `uploaded/total`、反推 `tagged/total`）+「查看详情」按钮（`batchId` 存在时跳 `/batch/:id`）；移除局部 `batchId/total` |
| `components/BatchProgress.vue` | **删除**（SSE 订阅职责移入 `useBatch`） |
| **新增** `components/BatchBars.vue` | 「双进度条」纯展示组件，接收 `useBatch().state` 渲染上传条 + 反推条；上传页内联 + 详情页顶部复用 |
| **新增** `views/BatchDetailPage.vue` | 顶部：双进度条 + 统计（`done=tagged+failed` / `total` / `failed`）；下方：`items` 明细表（名称、状态徽标 pending/ok/error、错误 msg） |
| `router.ts` | 加 `{ path: '/batch/:id', component: BatchDetailPage, props: true }` |

## 7. UI 细节

- **导航徽章**：处理中 `↑12/50 · ↓5/50`（上箭头=上传、下箭头=反推）；上传阶段反推段为 `↓0/50`；`done` 显示「✓ 完成 50」2 秒后淡出；`idle` 不渲染。`batchId` 存在则整个徽章可点击进详情页。
- **UploadPage 处理中**：`n-upload` 与「开始」按钮 `disabled`，鼠标悬停提示「处理中，请等待当前批次完成」。
- **双进度条**：`n-progress` 两条。上传条 `percentage = round(uploaded*100/total)`，反推条 `percentage = round(tagged*100/total)`；上传阶段反推条保持 0%。
- **详情页明细表**：每行 `name | 状态 n-tag(绿 ok / 红 error / 灰 pending) | msg`。

## 8. 边界与错误处理

- **切页**：store 与 ES 在模块层，组件卸载不影响 → 回到上传页进度完整恢复。
- **刷新 / 关页**：状态丢失回到 `idle`（取舍 1-a，接受）。
- **上传单张失败**：记 `items[i].error`，继续其余；全部失败则 `phase='error'`。
- **反推单张失败**：SSE `error` 事件 → `failed++`，`items` 标 error，不中断批次。
- **`autoTag=false`**：上传完直接 `done`，无反推段、无 `batchId`（徽章不跳转）。
- **重复提交**：`isBusy` 时按钮禁用，物理上无法再次 `start`。

## 9. 不做（YAGNI）

- 刷新 / 重开后用 `status` 轮询恢复进度。
- 处理中排队追加新批次（完全禁用，等当前完成）。
- 多批次并发管理（一次一个批次）。

## 10. 测试（vitest）

`composables/__tests__/useBatch.test.ts`：

- `phase` 流转：`idle → uploading → tagging → done`（autoTag=true）；`idle → uploading → done`（autoTag=false）。
- 逐张上传后 `uploaded`/`total` 正确，`items` 数量与状态。
- SSE `progress`/`error`/`done` 事件后 `tagged`/`failed`/`phase` 正确。
- 全部上传失败 → `phase='error'`。
- `isBusy()` 在 uploading/tagging 为 true，其余 false。
- `reset()` 清空所有字段并关闭 ES。
- mock `uploadOne`/`startBatch`/`EventSource`（构造假事件触发回调）。

现有 `detail.test.ts` 不受影响。
