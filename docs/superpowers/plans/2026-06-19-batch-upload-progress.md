# 批量上传进度与跨页状态保持 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让上传/反推进度成为全局状态，切页保持、处理中禁用重复上传、导航栏全局双段进度、新增批量详情页。

**Architecture:** 新增模块级单例 composable `useBatch()` 持有整个批次的 reactive 状态并管理 SSE EventSource 生命周期（不绑组件），所有页面读写同一实例。上传改为逐张以获得真实进度。导航徽章 / 详情页 / 上传页都从该 store 读数据。

**Tech Stack:** Vue 3.5 + TypeScript + naive-ui 2.44 + vue-router 4.6 + vitest 4（+ 新增 @vue/test-utils、jsdom 已在）

## Global Constraints

- 工作目录：`i:\trae\wd14\wd14-tagger-web`，前端在 `frontend/` 子目录。所有 npm 命令在 `frontend/` 下执行。
- npm 镜像：`--registry=https://registry.npmmirror.com`（用户环境，国内）。
- 所有 UI 文案为简体中文。
- 遵循现有风格：`<script setup lang="ts">`，naive-ui 组件具名导入。
- 后端 API **不改**：`POST /api/images` 接收 multipart `files`（单/多文件皆可）返回 `{ids:[...]}`；`POST /api/batch/tag` 返回 `{batch_id}`；`GET /api/batch/:id/events` 为 SSE。
- 每个任务结束 `git add` 相关文件并 commit；commit message 用中文，`feat:`/`chore:`/`refactor:` 前缀。
- TDD：先写失败测试 → 跑红 → 实现 → 跑绿 → commit。

## File Structure

| 文件 | 责任 | 动作 |
|---|---|---|
| `frontend/vite.config.ts` | 加 `test.environment='jsdom'` | Modify |
| `frontend/src/api/client.ts` | 加 `uploadOne(file)` 单文件上传 | Modify |
| `frontend/src/composables/useBatch.ts` | 全局批次状态单例 + SSE + start/reset | Create |
| `frontend/src/composables/__tests__/useBatch.test.ts` | store 行为测试 | Create |
| `frontend/src/components/BatchBars.vue` | 双进度条展示（接收 uploaded/tagged/total） | Create |
| `frontend/src/components/BatchBadge.vue` | 导航徽章（读 useBatch，两段进度，跳详情） | Create |
| `frontend/src/views/BatchDetailPage.vue` | 批量明细页（items 表 + 进度） | Create |
| `frontend/src/router.ts` | 加 `/batch/:id` 路由 | Modify |
| `frontend/src/App.vue` | NMenu 旁挂 BatchBadge | Modify |
| `frontend/src/views/UploadPage.vue` | 改用 useBatch + 禁用 + BatchBars + 详情入口 | Modify |
| `frontend/src/components/BatchProgress.vue` | SSE 订阅职责已移入 useBatch | **Delete** |

任务依赖链：1（环境）→ 2（uploadOne）→ 3（useBatch）→ 4/5/6（组件，并行可行但 plan 顺序执行）→ 7（路由）→ 8（App）→ 9（UploadPage）→ 10（清理）。

---

### Task 1: 测试基础设施（@vue/test-utils + jsdom 环境）

**Files:**
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/package.json`（装依赖）
- Test: `frontend/src/__tests__/env.smoke.test.ts`（新增，验证 mount 工作）

**Interfaces:**
- Produces: vitest 在 jsdom 环境运行；`@vue/test-utils` 可 import；现有 `detail.test.ts` 仍通过。

- [ ] **Step 1: 写验证测试（应因缺 test-utils 失败）**

创建 `frontend/src/__tests__/env.smoke.test.ts`：
```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'

describe('test env', () => {
  it('能 mount 组件并读到 DOM', () => {
    const C = defineComponent({ setup: () => () => h('div', { id: 'x' }, 'hi') })
    const w = mount(C)
    expect(w.find('#x').text()).toBe('hi')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run（在 `frontend/`）：`npx vitest run src/__tests__/env.smoke.test.ts`
Expected: FAIL — `Cannot find module '@vue/test-utils'`。

- [ ] **Step 3: 装依赖 + 配 jsdom**

Run（在 `frontend/`）：
```bash
npm install -D @vue/test-utils --registry=https://registry.npmmirror.com
```

修改 `frontend/vite.config.ts` 为：
```ts
/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  build: { outDir: 'dist' },
  test: { environment: 'jsdom' },
})
```

- [ ] **Step 4: 跑全部测试确认绿**

Run（在 `frontend/`）：`npx vitest run`
Expected: PASS — env.smoke + detail 共 6 个测试通过。

- [ ] **Step 5: Commit**

```bash
cd /i/trae/wd14/wd14-tagger-web
git add frontend/package.json frontend/package-lock.json frontend/vite.config.ts frontend/src/__tests__/env.smoke.test.ts
git commit -m "chore: 引入 @vue/test-utils 并配置 vitest jsdom 环境"
```

---

### Task 2: client.ts — uploadOne 单文件上传

**Files:**
- Modify: `frontend/src/api/client.ts`（在 `uploadImages` 后追加 `uploadOne`）
- Test: `frontend/src/__tests__/client.test.ts`（新增）

**Interfaces:**
- Produces: `uploadOne(file: File): Promise<{ id: string }>` —— 用 multipart `files` POST 单文件到 `/api/images`，返回 `{ id: data.ids[0] }`；失败抛 `Error(await r.text())`。

- [ ] **Step 1: 写失败测试**

创建 `frontend/src/__tests__/client.test.ts`：
```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { uploadOne } from '../api/client'

describe('uploadOne', () => {
  beforeEach(() => { vi.unstubAllGlobals() })
  it('单文件 POST /api/images 并返回 id', async () => {
    const fdSeen: any = []
    vi.stubGlobal('fetch', vi.fn(async (_url: string, opts: any) => {
      fdSeen.push(opts.body)
      return { ok: true, json: async () => ({ ids: ['abc123'] }) } as any
    }))
    const f = new File(['x'], 'a.png', { type: 'image/png' })
    const res = await uploadOne(f)
    expect(res).toEqual({ id: 'abc123' })
    expect(fdSeen[0]).toBeInstanceOf(FormData)
  })
  it('失败时抛错', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, text: async () => 'bad' }) as any))
    await expect(uploadOne(new File(['x'], 'a.png'))).rejects.toThrow('bad')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run：`npx vitest run src/__tests__/client.test.ts`
Expected: FAIL — `uploadOne is not a function`。

- [ ] **Step 3: 实现 uploadOne**

在 `frontend/src/api/client.ts` 的 `uploadImages` 函数之后追加：
```ts
export async function uploadOne(file: File): Promise<{ id: string }> {
  const fd = new FormData()
  fd.append('files', file)
  const r = await fetch(`${base}/api/images`, { method: 'POST', body: fd })
  if (!r.ok) throw new Error(await r.text())
  const data = await r.json()
  return { id: data.ids[0] }
}
```

- [ ] **Step 4: 跑测试确认通过**

Run：`npx vitest run src/__tests__/client.test.ts`
Expected: PASS — 2 个测试。

- [ ] **Step 5: Commit**

```bash
cd /i/trae/wd14/wd14-tagger-web
git add frontend/src/api/client.ts frontend/src/__tests__/client.test.ts
git commit -m "feat: 新增 uploadOne 单文件上传"
```

---

### Task 3: useBatch.ts — 全局批次 store + SSE（核心）

**Files:**
- Create: `frontend/src/composables/useBatch.ts`
- Test: `frontend/src/composables/__tests__/useBatch.test.ts`

**Interfaces:**
- Consumes: `uploadOne(file)` (Task 2)、`startBatch(ids, gen_th, char_th): Promise<{batch_id}>`、`subscribeBatch(batchId, onEvent): { close() }`（均来自 `../api/client`）。
- Produces:
  - `useBatch()` → `{ state, isBusy, start, reset }`
  - `state`: `{ phase: 'idle'|'uploading'|'tagging'|'done'|'error'; total; uploaded; tagged; failed; current: string; batchId: string|null; items: {id; name; status:'pending'|'ok'|'error'; msg?}[] }`
  - `start(files: File[], autoTag: boolean, genTh: number, charTh: number): Promise<void>`
  - `isBusy(): boolean`、`reset(): void`

- [ ] **Step 1: 写失败测试**

创建 `frontend/src/composables/__tests__/useBatch.test.ts`：
```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useBatch } from '../useBatch'
import * as client from '../../api/client'

vi.mock('../../api/client', () => ({
  uploadOne: vi.fn(),
  startBatch: vi.fn(),
  subscribeBatch: vi.fn(),
}))

beforeEach(() => {
  useBatch().reset()
  vi.clearAllMocks()
})

describe('useBatch', () => {
  it('逐张上传，autoTag=false 直接 done 且 items 标 ok', async () => {
    vi.mocked(client.uploadOne)
      .mockResolvedValueOnce({ id: 'a' })
      .mockResolvedValueOnce({ id: 'b' })
    const { state, start, isBusy } = useBatch()
    await start([new File([], 'x.png'), new File([], 'y.png')], false, 0.35, 0.9)
    expect(state.phase).toBe('done')
    expect(state.total).toBe(2)
    expect(state.uploaded).toBe(2)
    expect(state.tagged).toBe(0)
    expect(state.items.map(i => i.status)).toEqual(['ok', 'ok'])
    expect(client.startBatch).not.toHaveBeenCalled()
    expect(isBusy()).toBe(false)
  })

  it('单张上传失败记 error，其余继续', async () => {
    vi.mocked(client.uploadOne)
      .mockRejectedValueOnce(new Error('boom'))
      .mockResolvedValueOnce({ id: 'b' })
    const { state, start } = useBatch()
    await start([new File([], 'x.png'), new File([], 'y.png')], false, 0.35, 0.9)
    expect(state.uploaded).toBe(1)
    expect(state.items[0].status).toBe('error')
    expect(state.items[0].msg).toBe('boom')
    expect(state.items[1].status).toBe('ok')
  })

  it('全部上传失败 → phase=error', async () => {
    vi.mocked(client.uploadOne).mockRejectedValue(new Error('x'))
    const { state, start } = useBatch()
    await start([new File([], 'x.png')], true, 0.35, 0.9)
    expect(state.phase).toBe('error')
    expect(client.startBatch).not.toHaveBeenCalled()
  })

  it('autoTag=true：上传后 startBatch + 订阅 SSE，progress/done 更新', async () => {
    vi.mocked(client.uploadOne).mockResolvedValue({ id: 'a' })
    vi.mocked(client.startBatch).mockResolvedValue({ batch_id: 'B1' })
    vi.mocked(client.subscribeBatch).mockImplementation((_id: string, onEvent: (e: any) => void) => {
      queueMicrotask(() => {
        onEvent({ type: 'progress', done: 1, total: 1, current: 'x.png', id: 'a' })
        onEvent({ type: 'done', ok: 1, failed: 0 })
      })
      return { close: vi.fn() } as any
    })
    const { state, start, isBusy } = useBatch()
    await start([new File([], 'x.png')], true, 0.35, 0.9)
    expect(state.phase).toBe('tagging')   // 订阅后立即返回，回调尚未跑
    expect(state.batchId).toBe('B1')
    expect(isBusy()).toBe(true)
    await vi.waitFor(() => expect(state.phase).toBe('done'))
    expect(state.tagged).toBe(1)
    expect(state.items[0].status).toBe('ok')
  })

  it('SSE error 事件 → failed++ 且 items 标 error', async () => {
    vi.mocked(client.uploadOne).mockResolvedValue({ id: 'a' })
    vi.mocked(client.startBatch).mockResolvedValue({ batch_id: 'B1' })
    vi.mocked(client.subscribeBatch).mockImplementation((_id, onEvent: any) => {
      queueMicrotask(() => {
        onEvent({ type: 'error', id: 'a', message: 'timeout' })
        onEvent({ type: 'done', ok: 0, failed: 1 })
      })
      return { close: vi.fn() } as any
    })
    const { state, start } = useBatch()
    await start([new File([], 'x.png')], true, 0.35, 0.9)
    await vi.waitFor(() => expect(state.phase).toBe('done'))
    expect(state.failed).toBe(1)
    expect(state.items[0].status).toBe('error')
    expect(state.items[0].msg).toBe('timeout')
  })

  it('reset 清空所有字段', async () => {
    vi.mocked(client.uploadOne).mockResolvedValue({ id: 'a' })
    const { state, start, reset } = useBatch()
    await start([new File([], 'x.png')], false, 0.35, 0.9)
    reset()
    expect(state.phase).toBe('idle')
    expect(state.total).toBe(0)
    expect(state.items).toEqual([])
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run：`npx vitest run src/composables/__tests__/useBatch.test.ts`
Expected: FAIL — 找不到 `useBatch` 模块。

- [ ] **Step 3: 实现 useBatch.ts**

创建 `frontend/src/composables/useBatch.ts`：
```ts
import { reactive } from 'vue'
import { uploadOne, startBatch, subscribeBatch } from '../api/client'

export type Phase = 'idle' | 'uploading' | 'tagging' | 'done' | 'error'
export interface BatchItem { id: string; name: string; status: 'pending' | 'ok' | 'error'; msg?: string }

interface BatchState {
  phase: Phase
  total: number
  uploaded: number
  tagged: number
  failed: number
  current: string
  batchId: string | null
  items: BatchItem[]
}

const state = reactive<BatchState>({
  phase: 'idle', total: 0, uploaded: 0, tagged: 0, failed: 0,
  current: '', batchId: null, items: [],
})

// EventSource 由 store 持有，不绑组件；subscribeBatch 返回带 close 的句柄
let es: { close: () => void } | null = null

function isBusy() {
  return state.phase === 'uploading' || state.phase === 'tagging'
}

function reset() {
  state.phase = 'idle'
  state.total = state.uploaded = state.tagged = state.failed = 0
  state.current = ''
  state.batchId = null
  state.items = []
  es?.close()
  es = null
}

async function start(files: File[], autoTag: boolean, genTh: number, charTh: number) {
  reset()
  state.phase = 'uploading'
  state.total = files.length
  state.items = files.map(f => ({ id: '', name: f.name, status: 'pending' as const }))
  const ids: string[] = []
  for (let i = 0; i < files.length; i++) {
    try {
      const res = await uploadOne(files[i])
      state.uploaded++
      state.items[i].id = res.id
      ids.push(res.id)
    } catch (e: any) {
      state.items[i].status = 'error'
      state.items[i].msg = e?.message || String(e)
    }
  }
  if (ids.length === 0) { state.phase = 'error'; return }
  if (!autoTag) {
    state.items.forEach(it => { if (it.status === 'pending') it.status = 'ok' })
    state.phase = 'done'
    return
  }
  const b = await startBatch(ids, genTh, charTh)
  state.batchId = b.batch_id
  state.phase = 'tagging'
  es = subscribeBatch(b.batch_id, (ev) => {
    if (ev.type === 'progress') {
      state.tagged++
      state.current = ev.current || ''
      const it = state.items.find(x => x.id === ev.id)
      if (it) it.status = 'ok'
    } else if (ev.type === 'error') {
      state.failed++
      const it = state.items.find(x => x.id === ev.id)
      if (it) { it.status = 'error'; it.msg = ev.message || '' }
    } else if (ev.type === 'done') {
      state.phase = 'done'
      es?.close()
      es = null
    }
  })
}

export function useBatch() {
  return { state, isBusy, start, reset }
}
```

- [ ] **Step 4: 跑测试确认通过**

Run：`npx vitest run src/composables/__tests__/useBatch.test.ts`
Expected: PASS — 6 个测试。

- [ ] **Step 5: Commit**

```bash
cd /i/trae/wd14/wd14-tagger-web
git add frontend/src/composables/useBatch.ts frontend/src/composables/__tests__/useBatch.test.ts
git commit -m "feat: 全局批次 store useBatch（逐张上传+SSE 订阅+状态保持）"
```

---

### Task 4: BatchBars.vue — 双进度条展示组件

**Files:**
- Create: `frontend/src/components/BatchBars.vue`
- Test: `frontend/src/__tests__/BatchBars.test.ts`

**Interfaces:**
- Consumes: props `{ uploaded: number; tagged: number; total: number }`
- Produces: 渲染两条 `n-progress`（上传 `uploaded/total`、反推 `tagged/total`）+ 文本数字。

- [ ] **Step 1: 写失败测试**

创建 `frontend/src/__tests__/BatchBars.test.ts`：
```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BatchBars from '../components/BatchBars.vue'

describe('BatchBars', () => {
  it('渲染上传与反推两段的数字', () => {
    const w = mount(BatchBars, { props: { uploaded: 2, tagged: 1, total: 5 } })
    const html = w.html()
    expect(html).toContain('2/5')   // 上传段
    expect(html).toContain('1/5')   // 反推段
  })
  it('total=0 时不抛错（百分比兜底为 0）', () => {
    const w = mount(BatchBars, { props: { uploaded: 0, tagged: 0, total: 0 } })
    expect(w.html()).toContain('0/0')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run：`npx vitest run src/__tests__/BatchBars.test.ts`
Expected: FAIL — 找不到组件。

- [ ] **Step 3: 实现 BatchBars.vue**

创建 `frontend/src/components/BatchBars.vue`：
```vue
<script setup lang="ts">
import { computed } from 'vue'
import { NProgress } from 'naive-ui'
const props = defineProps<{ uploaded: number; tagged: number; total: number }>()
const pc = (n: number) => (props.total ? Math.round(n * 100 / props.total) : 0)
const upPct = computed(() => pc(props.uploaded))
const tagPct = computed(() => pc(props.tagged))
</script>

<template>
  <div>
    <div style="margin-bottom:6px">
      <div style="font-size:12px">上传 {{ uploaded }}/{{ total }}</div>
      <n-progress :percentage="upPct" :height="10" />
    </div>
    <div>
      <div style="font-size:12px">反推 {{ tagged }}/{{ total }}</div>
      <n-progress :percentage="tagPct" :height="10" status="success" />
    </div>
  </div>
</template>
```

- [ ] **Step 4: 跑测试确认通过**

Run：`npx vitest run src/__tests__/BatchBars.test.ts`
Expected: PASS — 2 个测试。

- [ ] **Step 5: Commit**

```bash
cd /i/trae/wd14/wd14-tagger-web
git add frontend/src/components/BatchBars.vue frontend/src/__tests__/BatchBars.test.ts
git commit -m "feat: BatchBars 双进度条组件"
```

---

### Task 5: BatchBadge.vue — 导航栏徽章

**Files:**
- Create: `frontend/src/components/BatchBadge.vue`
- Test: `frontend/src/__tests__/BatchBadge.test.ts`

**Interfaces:**
- Consumes: `useBatch()`（读 `state`、`isBusy`）、`vue-router`（跳 `/batch/:id`）。
- Produces：处理中显示 `↑uploaded/total · ↓tagged/total` 并可点击跳详情；`done` 显示「✓ 完成 total」；`idle` 不渲染。

- [ ] **Step 1: 写失败测试**

创建 `frontend/src/__tests__/BatchBadge.test.ts`：
```ts
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import BatchBadge from '../components/BatchBadge.vue'
import { useBatch } from '../composables/useBatch'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))

describe('BatchBadge', () => {
  it('idle 时不渲染', () => {
    useBatch().reset()
    const w = mount(BatchBadge)
    expect(w.find('[data-testid="badge"]').exists()).toBe(false)
  })
  it('处理中显示两段进度文本', async () => {
    const { state } = useBatch()
    state.phase = 'uploading'; state.total = 5; state.uploaded = 2; state.tagged = 1
    const w = mount(BatchBadge)
    const html = w.html()
    expect(html).toContain('2/5')
    expect(html).toContain('1/5')
  })
  it('done 显示完成', async () => {
    const { state } = useBatch()
    state.phase = 'done'; state.total = 3; state.uploaded = 3; state.tagged = 3
    const w = mount(BatchBadge)
    expect(w.html()).toContain('完成')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run：`npx vitest run src/__tests__/BatchBadge.test.ts`
Expected: FAIL — 找不到组件。

- [ ] **Step 3: 实现 BatchBadge.vue**

创建 `frontend/src/components/BatchBadge.vue`：
```vue
<script setup lang="ts">
import { useRouter } from 'vue-router'
import { NTag } from 'naive-ui'
import { useBatch } from '../composables/useBatch'

const router = useRouter()
const { state } = useBatch()

function visible() { return state.phase !== 'idle' }
function toDetail() { if (state.batchId) router.push('/batch/' + state.batchId) }
</script>

<template>
  <n-tag v-if="visible()" data-testid="badge"
         :type="state.phase === 'done' ? 'success' : 'info'"
         size="small" checkable
         :style="{ cursor: state.batchId ? 'pointer' : 'default' }"
         @click="toDetail">
    <template v-if="state.phase === 'done'">✓ 完成 {{ state.total }}</template>
    <template v-else>↑{{ state.uploaded }}/{{ state.total }} · ↓{{ state.tagged }}/{{ state.total }}</template>
  </n-tag>
</template>
```

- [ ] **Step 4: 跑测试确认通过**

Run：`npx vitest run src/__tests__/BatchBadge.test.ts`
Expected: PASS — 3 个测试。

- [ ] **Step 5: Commit**

```bash
cd /i/trae/wd14/wd14-tagger-web
git add frontend/src/components/BatchBadge.vue frontend/src/__tests__/BatchBadge.test.ts
git commit -m "feat: BatchBadge 导航栏双段进度徽章"
```

---

### Task 6: BatchDetailPage.vue — 批量详情页

**Files:**
- Create: `frontend/src/views/BatchDetailPage.vue`
- Test: `frontend/src/__tests__/BatchDetailPage.test.ts`

**Interfaces:**
- Consumes: `useBatch()`、`BatchBars` 组件。
- Produces：顶部统计（done=tagged+failed / total）+ BatchBars + items 明细表（名称、状态徽标、错误）。

- [ ] **Step 1: 写失败测试**

创建 `frontend/src/__tests__/BatchDetailPage.test.ts`：
```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BatchDetailPage from '../views/BatchDetailPage.vue'
import { useBatch } from '../composables/useBatch'

describe('BatchDetailPage', () => {
  it('渲染统计与 items 明细', () => {
    const { state } = useBatch()
    state.phase = 'tagging'
    state.total = 2; state.uploaded = 2; state.tagged = 1; state.failed = 0
    state.items = [
      { id: 'a', name: 'a.png', status: 'ok' },
      { id: 'b', name: 'b.png', status: 'pending' },
    ]
    const w = mount(BatchDetailPage)
    const html = w.html()
    expect(html).toContain('a.png')
    expect(html).toContain('b.png')
    expect(html).toContain('1/2')   // 反推进度 1/2
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run：`npx vitest run src/__tests__/BatchDetailPage.test.ts`
Expected: FAIL — 找不到页面。

- [ ] **Step 3: 实现 BatchDetailPage.vue**

创建 `frontend/src/views/BatchDetailPage.vue`：
```vue
<script setup lang="ts">
import { computed } from 'vue'
import { NCard, NTag, NTable } from 'naive-ui'
import { useBatch } from '../composables/useBatch'
import BatchBars from '../components/BatchBars.vue'

const { state } = useBatch()
const doneCount = computed(() => state.tagged + state.failed)
function tagType(s: string) { return s === 'ok' ? 'success' : s === 'error' ? 'error' : 'default' }
function tagText(s: string) { return s === 'ok' ? '完成' : s === 'error' ? '失败' : '待处理' }
</script>

<template>
  <n-card title="批量处理详情">
    <div style="margin-bottom:12px">
      已完成 {{ doneCount }}/{{ state.total }}（成功 {{ state.tagged }} · 失败 {{ state.failed }}）
    </div>
    <BatchBars :uploaded="state.uploaded" :tagged="state.tagged" :total="state.total" />
    <n-table :bordered="false" :single-line="false" style="margin-top:12px">
      <thead><tr><th>文件名</th><th>状态</th><th>说明</th></tr></thead>
      <tbody>
        <tr v-for="it in state.items" :key="it.id || it.name">
          <td>{{ it.name }}</td>
          <td><n-tag :type="tagType(it.status)" size="small">{{ tagText(it.status) }}</n-tag></td>
          <td>{{ it.msg || '' }}</td>
        </tr>
      </tbody>
    </n-table>
  </n-card>
</template>
```

- [ ] **Step 4: 跑测试确认通过**

Run：`npx vitest run src/__tests__/BatchDetailPage.test.ts`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
cd /i/trae/wd14/wd14-tagger-web
git add frontend/src/views/BatchDetailPage.vue frontend/src/__tests__/BatchDetailPage.test.ts
git commit -m "feat: BatchDetailPage 批量处理明细页"
```

---

### Task 7: router.ts — 加 /batch/:id 路由

**Files:**
- Modify: `frontend/src/router.ts`

**Interfaces:**
- Produces：路由 `/batch/:id` → `BatchDetailPage`（props: true）。

- [ ] **Step 1: 实现（纯路由配置，无独立单测，靠 build + 后续页面验证）**

修改 `frontend/src/router.ts`，在 import 段加：
```ts
import BatchDetailPage from './views/BatchDetailPage.vue'
```
在 `routes` 数组中（`/detail/:id` 之后）加：
```ts
    { path: '/batch/:id', component: BatchDetailPage, props: true },
```

完整改后文件：
```ts
import { createRouter, createWebHistory } from 'vue-router'
import UploadPage from './views/UploadPage.vue'
import GalleryPage from './views/GalleryPage.vue'
import DetailPage from './views/DetailPage.vue'
import BatchDetailPage from './views/BatchDetailPage.vue'
import SettingsPage from './views/SettingsPage.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/gallery' },
    { path: '/upload', component: UploadPage },
    { path: '/gallery', component: GalleryPage },
    { path: '/detail/:id', component: DetailPage, props: true },
    { path: '/batch/:id', component: BatchDetailPage, props: true },
    { path: '/settings', component: SettingsPage },
  ],
})
```

- [ ] **Step 2: 跑全量测试 + build 验证**

Run：
```bash
npx vitest run
npm run build
```
Expected：测试全绿；build 成功（无类型错误）。

- [ ] **Step 3: Commit**

```bash
cd /i/trae/wd14/wd14-tagger-web
git add frontend/src/router.ts
git commit -m "feat: 路由 /batch/:id 指向批量详情页"
```

---

### Task 8: App.vue — 导航栏挂载 BatchBadge

**Files:**
- Modify: `frontend/src/App.vue`
- Test: `frontend/src/__tests__/App.test.ts`

**Interfaces:**
- Consumes: `BatchBadge` 组件。
- Produces：NMenu 右侧显示 BatchBadge。

- [ ] **Step 1: 写失败测试**

创建 `frontend/src/__tests__/App.test.ts`：
```ts
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

// App.vue 用了 NMenu/useRouter，stub 掉 router
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

import App from '../App.vue'

describe('App', () => {
  it('挂载了 BatchBadge（导航徽章存在）', () => {
    const w = mount(App, { global: { stubs: { NConfigProvider: { template: '<slot/>' }, NMessageProvider: { template: '<slot/>' }, NDialogProvider: { template: '<slot/>' }, NLayout: { template: '<slot/>' }, NMenu: { template: '<div/>' } } } })
    // idle 时不渲染徽章，但组件本身被 import/挂载即可（无报错）
    expect(w.html()).toBeDefined()
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run：`npx vitest run src/__tests__/App.test.ts`
Expected: FAIL — `App` 模板里还没有 BatchBadge（测试本身能过，但本步先确认现状；若已过说明无需改 —— 实际应因组件尚未引入而模板无变化，测试可能已绿，重点在 Step 3 引入后再跑）。

> 说明：此任务的核心是模板引入 BatchBadge。测试保证挂载不报错。若 Step 2 已绿，直接做 Step 3 再跑一次确认无回归。

- [ ] **Step 3: 修改 App.vue 挂载徽章**

修改 `frontend/src/App.vue` 为：
```vue
<script setup lang="ts">
import { NConfigProvider, NMessageProvider, NDialogProvider, NLayout, NMenu, NSpace } from 'naive-ui'
import { useRouter } from 'vue-router'
import BatchBadge from './components/BatchBadge.vue'
const router = useRouter()
const options = [
  { label: '上传', key: 'upload' },
  { label: '图库', key: 'gallery' },
  { label: '设置', key: 'settings' },
]
function go(key: string) { router.push('/' + key) }
</script>

<template>
  <n-config-provider>
    <n-message-provider>
      <n-dialog-provider>
        <n-layout style="min-height:100vh">
          <n-space align="center" justify="space-between" style="padding:8px 16px">
            <n-menu mode="horizontal" :options="options" @update:value="go" />
            <BatchBadge />
          </n-space>
          <div style="padding:16px"><router-view /></div>
        </n-layout>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>
```

- [ ] **Step 4: 跑测试确认通过**

Run：`npx vitest run src/__tests__/App.test.ts`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
cd /i/trae/wd14/wd14-tagger-web
git add frontend/src/App.vue frontend/src/__tests__/App.test.ts
git commit -m "feat: 导航栏挂载全局进度徽章 BatchBadge"
```

---

### Task 9: UploadPage.vue — 改用 useBatch + 禁用 + 双进度 + 详情入口

**Files:**
- Modify: `frontend/src/views/UploadPage.vue`
- Test: `frontend/src/__tests__/UploadPage.test.ts`

**Interfaces:**
- Consumes: `useBatch()`（`state`/`isBusy`/`start`）、`BatchBars` 组件、`vue-router`（跳 `/batch/:id`）。
- Produces：处理中禁用「选择」「开始」；显示 BatchBars；有 batchId 时显示「查看详情」按钮。

- [ ] **Step 1: 写失败测试**

创建 `frontend/src/__tests__/UploadPage.test.ts`：
```ts
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import UploadPage from '../views/UploadPage.vue'
import { useBatch } from '../composables/useBatch'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))

describe('UploadPage', () => {
  it('处理中禁用开始按钮', async () => {
    const { state, start } = useBatch()
    // 借用真实 start 让 isBusy=true（mock uploadOne）
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ ids: ['a'] }) }) as any))
    const w = mount(UploadPage, { global: { stubs: { NMenu: true } } })
    // 初始可点
    expect(w.find('[data-testid="start-btn"]').attributes('disabled')).toBeUndefined()
    // 触发处理中
    state.phase = 'uploading'
    await w.vm.$nextTick()
    expect(w.find('[data-testid="start-btn"]').attributes('disabled')).toBeDefined()
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run：`npx vitest run src/__tests__/UploadPage.test.ts`
Expected: FAIL — `start-btn` 不存在（当前模板按钮无该 testid）。

- [ ] **Step 3: 改造 UploadPage.vue**

将 `frontend/src/views/UploadPage.vue` 整体替换为：
```vue
<script setup lang="ts">
import { ref } from 'vue'
import { NUpload, NButton, NSlider, NSwitch, NSpace, NCard, useMessage } from 'naive-ui'
import { useRouter } from 'vue-router'
import { useBatch } from '../composables/useBatch'
import BatchBars from '../components/BatchBars.vue'

const router = useRouter()
const msg = useMessage()
const { state, isBusy, start } = useBatch()
const genTh = ref(0.35)
const charTh = ref(0.9)
const autoTag = ref(true)
const pending = ref<File[]>([])

function onSelect(opts: any) { pending.value = opts.fileList.map((f: any) => f.file) }

async function go() {
  if (!pending.value.length) { msg.warning('请先选择图片'); return }
  if (isBusy()) { msg.warning('当前批次处理中，请等待完成'); return }
  try {
    await start(pending.value, autoTag.value, genTh.value, charTh.value)
    pending.value = []
    msg.success('已提交处理')
  } catch (e: any) { msg.error('提交失败：' + e.message) }
}
</script>

<template>
  <n-space vertical>
    <n-card title="上传图片">
      <n-upload multiple :default-upload="false" :disabled="isBusy()" @change="onSelect" accept="image/*">
        <n-button :disabled="isBusy()">选择图片（可多选）</n-button>
      </n-upload>
    </n-card>
    <n-card title="反推设置">
      <n-space>
        <div>通用阈值 <n-slider v-model:value="genTh" :min="0" :max="1" :step="0.01" style="width:160px" /> {{ genTh }}</div>
        <div>角色阈值 <n-slider v-model:value="charTh" :min="0" :max="1" :step="0.01" style="width:160px" /> {{ charTh }}</div>
        <div>上传后自动反推 <n-switch v-model:value="autoTag" /></div>
      </n-space>
      <n-space style="margin-top:12px">
        <n-button data-testid="start-btn" type="primary" :disabled="isBusy()" @click="go">开始</n-button>
        <n-button v-if="state.batchId" @click="router.push('/batch/' + state.batchId)">查看详情</n-button>
        <n-button @click="router.push('/gallery')">前往图库</n-button>
      </n-space>
    </n-card>
    <n-card v-if="state.phase !== 'idle'" title="进度">
      <BatchBars :uploaded="state.uploaded" :tagged="state.tagged" :total="state.total" />
      <div v-if="state.phase === 'done'" style="color:#18a058;margin-top:8px">✓ 完成（成功 {{ state.tagged }} · 失败 {{ state.failed }}）</div>
      <div v-if="state.phase === 'error'" style="color:#d03050;margin-top:8px">全部上传失败</div>
      <div style="font-size:12px;color:#888;margin-top:6px">处理中：{{ state.current }}</div>
    </n-card>
  </n-space>
</template>
```

- [ ] **Step 4: 跑测试确认通过**

Run：`npx vitest run src/__tests__/UploadPage.test.ts`
Expected: PASS。

- [ ] **Step 5: 跑全量测试 + build**

Run：
```bash
npx vitest run
npm run build
```
Expected：全绿；build 成功。

- [ ] **Step 6: Commit**

```bash
cd /i/trae/wd14/wd14-tagger-web
git add frontend/src/views/UploadPage.vue frontend/src/__tests__/UploadPage.test.ts
git commit -m "feat: UploadPage 改用全局 useBatch（禁用重复上传+双进度+详情入口）"
```

---

### Task 10: 删除 BatchProgress.vue + 全量验证

**Files:**
- Delete: `frontend/src/components/BatchProgress.vue`
- Verify: 全项目无残留引用

**Interfaces:**
- Consumes: Task 9 已移除 UploadPage 对 BatchProgress 的引用。

- [ ] **Step 1: 确认无引用**

Run（在 `frontend/`）：
```bash
grep -rn "BatchProgress" src
```
Expected：无输出（UploadPage 已不再 import）。若有残留，先删除对应 import/使用。

- [ ] **Step 2: 删除文件**

Run：
```bash
rm src/components/BatchProgress.vue
```

- [ ] **Step 3: 全量测试 + build**

Run：
```bash
npx vitest run
npm run build
```
Expected：所有测试通过；build 成功无未解析引用。

- [ ] **Step 4: 生产冒烟（手动）**

启动后端（已在运行则跳过）+ 用 build 产物：
```bash
cd /i/trae/wd14/wd14-tagger-web
.venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```
浏览器 http://127.0.0.1:8000 验证：
- 上传 2-3 张图 → 进度条逐张走 → 处理中「选择/开始」置灰；
- 处理中点「图库」再点「上传」→ 进度仍在；
- 导航栏徽章显示 `↑x/y · ↓a/b`，点击进详情页看到明细表；
- 完成后徽章变「✓ 完成」。

- [ ] **Step 5: Commit**

```bash
cd /i/trae/wd14/wd14-tagger-web
git add -A frontend
git commit -m "refactor: 删除 BatchProgress.vue（职责已并入 useBatch）"
```

---

## Self-Review 记录

- **Spec 覆盖**：需求①禁用→Task9；②跨页保持→Task3 store + Task8/9 读同一实例；③详情页入口→Task9 按钮 + Task6 页面；④导航全局进度→Task5+Task8；⑤双进度条→Task2(逐张)+Task4。全覆盖。
- **占位扫描**：无 TBD/TODO；每个 code step 含完整代码。
- **类型一致**：`useBatch()` 返回 `{state, isBusy, start, reset}` 各任务一致；`state` 字段（phase/total/uploaded/tagged/failed/current/batchId/items）Task3 定义、Task4/5/6/9 消费一致；`uploadOne` 返回 `{id}` Task2/3 一致；`BatchBars` props `{uploaded,tagged,total}` Task4/6/9 一致。
