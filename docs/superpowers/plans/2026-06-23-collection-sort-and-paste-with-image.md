# 收藏列表新增在前 + 提示词收藏「粘贴拆分（可附图）」实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 收藏列表按创建时间倒序（新增在前）；提示词收藏工作台新增「粘贴拆分（可附图）」入口，粘贴自写提示词 + 选图（不反推）产带图工作区项。

**Architecture:** 需求1 纯前端——`CollectionListPage` 的 `filtered` computed 末尾按 `created_at` 倒序。需求2 前后端——后端新增 `POST /api/promptbox/workspace/image`（复用 `save_workspace_image`，不调 tagger），前端 `client.ts` 加上传函数、`PromptBoxPage.vue` 新增独立「粘贴拆分（可附图）」卡片（与「拆分编辑（选中项）」同行左右排列），顶部无图粘贴拆分保留。

**Tech Stack:** Vue 3 `<script setup lang="ts">` + Naive UI + vue-router；FastAPI（后端）；Vitest + @vue/test-utils（前端测试）。

## Global Constraints

- 顶部「上传反推」卡片里的「粘贴拆分（无图）」**保留不动**（用户明确：它用于"只想拆分提示词、不存图"）。
- 附图**可选**：附图→带图项（主场景），不附图→无图项（退化）。
- 后端新端点 `POST /api/promptbox/workspace/image` **只存图不反推**，复用 `store.save_workspace_image`，注册位置紧跟 `analyze`、在 `/{item_id}` 之前。
- 排序在 `filtered` computed 内、按 `created_at` 字符串 `localeCompare` **倒序**；不动后端、不动 `RandomPage`。
- **本项目后端无 pytest 套件**：遵循既有零后端测试惯例，后端端点靠手动 curl 验证 + 前端 vitest 间接覆盖，**不新建 pytest 框架**。
- 整合包同步：前端 `npm run build` 产 dist 后 cp 到两处整合包；后端 `routes_promptbox.py` cp 到两处整合包同路径。**只 cp 文件，绝不重新打包**（`pack_portable.py` 会清空用户数据，且该文件用户正在改、严禁 `git add`/触碰）。
- 当前已在分支 `feat-collection-sort-and-paste-with-image`；每个 commit 只 `git add` 本任务相关文件，**不要 add `pack_portable.py`**。
- 前端测试运行：在 `wd14-tagger-web/frontend` 目录 `npx vitest run src/__tests__/<file>.test.ts`。
- 前端构建：在 `wd14-tagger-web/frontend` 目录 `npm run build`（= `vue-tsc -b && vite build`）。

---

### Task 1: 收藏列表按 created_at 倒序（新增在前）

**Files:**
- Modify: `wd14-tagger-web/frontend/src/views/CollectionListPage.vue`（`filtered` computed，约第 28-35 行）
- Test: `wd14-tagger-web/frontend/src/__tests__/CollectionListPage.test.ts`（已存在，增补用例）

**Interfaces:**
- Consumes: `listPromptbox()` 返回的 `PromptboxItem[]`（每项含 `created_at: string`，ISO 字符串）。
- Produces: `filtered` computed 仍为 `PromptboxItem[]`，但顺序改为 `created_at` 倒序；`paged`/模板无需改动（继承 `filtered` 顺序）。

- [ ] **Step 1: 写失败测试**

在 `CollectionListPage.test.ts` 的 `describe` 块末尾追加：

```ts
  it('按 created_at 倒序：新增的排最前', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url === '/api/promptbox') return { ok: true, json: async () => [
        { id: 'old', title: '旧收藏', raw_prompt: 'a', categories: {}, extras: [], image_names: [], created_at: '2026-06-01T10:00:00+08:00', updated_at: '' },
        { id: 'mid', title: '中收藏', raw_prompt: 'b', categories: {}, extras: [], image_names: [], created_at: '2026-06-02T10:00:00+08:00', updated_at: '' },
        { id: 'new', title: '新收藏', raw_prompt: 'c', categories: {}, extras: [], image_names: [], created_at: '2026-06-03T10:00:00+08:00', updated_at: '' },
      ] } as any
      return { ok: true, json: async () => ({}) } as any
    }))
    const w = mount(CollectionListPage, { global: { stubs: { NMenu: true } } })
    await flushPromises()
    // 卡片 .title 按 DOM 顺序 = paged 顺序 = filtered 倒序
    const titles = w.findAll('.title').map(e => e.text())
    expect(titles).toEqual(['新收藏', '中收藏', '旧收藏'])
  })
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd wd14-tagger-web/frontend && npx vitest run src/__tests__/CollectionListPage.test.ts`
Expected: FAIL —— 新用例失败（当前顺序为升序 `['旧收藏','中收藏','新收藏']`，断言期望倒序）。

- [ ] **Step 3: 实现——filtered 末尾加倒序排序**

修改 `CollectionListPage.vue` 的 `filtered` computed，把 `return items.value` / `return items.value.filter(...)` 改为先收集到 `base`、再倒序返回：

```ts
const filtered = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  const base = k
    ? items.value.filter(it =>
        (it.title || '').toLowerCase().includes(k) ||
        (it.raw_prompt || '').toLowerCase().includes(k))
    : items.value
  // 新增在前：created_at 倒序（ISO 字符串 localeCompare 倒序 = 时间倒序）
  return [...base].sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))
})
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd wd14-tagger-web/frontend && npx vitest run src/__tests__/CollectionListPage.test.ts`
Expected: PASS（全部用例，含新增倒序用例与既有分页/搜索用例）。

- [ ] **Step 5: 提交**

```bash
cd wd14-tagger-web
git add frontend/src/views/CollectionListPage.vue frontend/src/__tests__/CollectionListPage.test.ts
git commit -m "feat: 收藏列表按 created_at 倒序，新增记录排最前"
```

---

### Task 2: 后端「只存图不反推」端点 workspace/image

**Files:**
- Modify: `wd14-tagger-web/backend/api/routes_promptbox.py`（在 `analyze` 路由之后、`/{item_id}` 路由之前新增端点）

**Interfaces:**
- Consumes: `get_promptbox_store()`（`deps.py`）、`store.save_workspace_image(local_id, pil, source_name) -> (original, thumb, w, h)`（`promptbox_store.py`，已存在）、`store.new_id()`。
- Produces: `POST /api/promptbox/workspace/image`，body 为 multipart `files`，返回 `{"items": [{"local_id", "original", "thumb", "width", "height"}]}`。**不调用** `get_tagger` / `get_classifier`。

**说明（无 pytest）：** 本项目后端无测试套件，遵循零后端测试惯例。本端点逻辑仅复用已验证的 `save_workspace_image`，正确性靠 Step 4 手动 curl 验证 + Task 3 前端 vitest（mock fetch 拦截 `/api/promptbox/workspace/image`）间接覆盖。

- [ ] **Step 1: 实现端点**

在 `routes_promptbox.py` 的 `analyze` 函数之后（`@router.get("/workspace/{local_id}/image/{name}")` 之前）插入：

```python
@router.post("/workspace/image")
def upload_workspace_image(files: list[UploadFile] = File(...)):
    """只存图到 workspace、不反推：供「粘贴拆分（可附图）」给自写提示词附图用。
    复用 save_workspace_image；不调 tagger/classifier。"""
    store = get_promptbox_store()
    out = []
    for f in files:
        try:
            pil = Image.open(f.file)
            pil.load()
        except (UnidentifiedImageError, OSError) as e:
            raise HTTPException(status_code=400, detail=f"bad image {f.filename}: {e}")
        local_id = store.new_id()
        orig, thumb, w, h = store.save_workspace_image(local_id, pil, f.filename or "img.png")
        out.append({"local_id": local_id, "original": orig, "thumb": thumb, "width": w, "height": h})
    return {"items": out}
```

> `Image`、`UnidentifiedImageError`、`HTTPException`、`UploadFile`、`File` 均已在文件顶部 import（见 `analyze` 用法），无需新增 import。

- [ ] **Step 2: 静态自检——确认路由注册顺序无冲突**

确认新端点 `@router.post("/workspace/image")` 位于 `@router.get("/workspace/{local_id}/image/{name}")` 与 `@router.post("/{item_id}/tag")` 等 `/{item_id}` 路由**之前**（紧跟 `analyze`）。FastAPI 按注册顺序匹配，`/workspace/...` 必须早于 `/{item_id}` 注册，否则首段 `workspace` 会被 `/{item_id}` 捕获。

- [ ] **Step 3: 提交**

```bash
cd wd14-tagger-web
git add backend/api/routes_promptbox.py
git commit -m "feat: promptbox 新增 workspace/image 端点（只存图不反推）"
```

- [ ] **Step 4: 手动验证（curl）**

启动后端（项目根目录 `uvicorn main:app`，或双击整合包 `启动.bat`），准备一张本地 png（例 `test.png`），执行：

```bash
curl -X POST -F "files=@test.png" http://localhost:8000/api/promptbox/workspace/image
```

Expected: HTTP 200，返回形如 `{"items":[{"local_id":"20260623-...","original":"original.png","thumb":"thumb.webp","width":...,"height":...}]}`；且后端 `data/promptbox/workspace/<local_id>/` 下存在 `original.png` 与 `thumb.webp`。再用一张非图文件验证 400：`curl -X POST -F "files=@some.txt" ...` → `{"detail":"bad image ..."}`。

---

### Task 3: 前端「粘贴拆分（可附图）」入口

**Files:**
- Modify: `wd14-tagger-web/frontend/src/api/client.ts`（新增 `WorkspaceImageInfo` 类型 + `uploadPromptboxWorkspaceImage` 函数）
- Modify: `wd14-tagger-web/frontend/src/views/PromptBoxPage.vue`（新增状态/逻辑 + 拆分编辑区布局改为左右两栏）
- Test: `wd14-tagger-web/frontend/src/__tests__/PromptBoxPage.test.ts`（已存在，增补 2 个用例）

**Interfaces:**
- Consumes: Task 2 的 `POST /api/promptbox/workspace/image`；既有 `splitPrompt(text)`。
- Produces: `uploadPromptboxWorkspaceImage(files: File[]): Promise<{items: WorkspaceImageInfo[]}>`；`PromptBoxPage` 内 `doPasteSplitWithImage()`（读 `pasteTextImg`/`pasteFile` ref）。

- [ ] **Step 1: 写失败测试**

在 `PromptBoxPage.test.ts` 的 `describe` 块末尾追加两个用例：

```ts
  it('粘贴+附图：调 workspace/image + split，产带图项', async () => {
    const calls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      calls.push(url)
      if (url === '/api/promptbox/workspace/image') {
        return { ok: true, json: async () => ({ items: [{
          local_id: 'ws9', original: 'original.png', thumb: 'thumb.webp', width: 10, height: 10,
        }] }) } as any
      }
      if (url === '/api/promptbox/split') {
        return { ok: true, json: async () => ({ categories: { head: ['long hair'] }, extras: [] }) } as any
      }
      return { ok: true, json: async () => ({ items: [] }) } as any
    }))
    const w = mount(PromptBoxPage, { global: { stubs: { NMenu: true } } })
    await flushPromises()
    ;(w.vm as any).pasteTextImg = 'long hair'
    ;(w.vm as any).pasteFile = new File(['x'], 'a.png')
    await (w.vm as any).doPasteSplitWithImage()
    await flushPromises()
    expect(calls).toContain('/api/promptbox/workspace/image')
    expect(calls).toContain('/api/promptbox/split')
    // 新建带图项被选中 → 拆分编辑区显示其分类标签
    expect(w.text()).toContain('long hair')
  })

  it('粘贴不附图：仅 split，不调 workspace/image', async () => {
    const calls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      calls.push(url)
      if (url === '/api/promptbox/split') {
        return { ok: true, json: async () => ({ categories: { head: ['cat'] }, extras: [] }) } as any
      }
      return { ok: true, json: async () => ({ items: [] }) } as any
    }))
    const w = mount(PromptBoxPage, { global: { stubs: { NMenu: true } } })
    await flushPromises()
    ;(w.vm as any).pasteTextImg = 'cat'
    ;(w.vm as any).pasteFile = null
    await (w.vm as any).doPasteSplitWithImage()
    await flushPromises()
    expect(calls).toContain('/api/promptbox/split')
    expect(calls.some(u => u === '/api/promptbox/workspace/image')).toBe(false)
    expect(w.text()).toContain('cat')
  })
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd wd14-tagger-web/frontend && npx vitest run src/__tests__/PromptBoxPage.test.ts`
Expected: FAIL —— `doPasteSplitWithImage` / `uploadPromptboxWorkspaceImage` 未定义。

- [ ] **Step 3: client.ts 新增上传函数**

在 `client.ts` 中 `analyzePromptbox` 函数附近（或 `promptboxWorkspaceImageUrl` 之前）新增：

```ts
export interface WorkspaceImageInfo {
  local_id: string; original: string; thumb: string; width: number; height: number
}
// 提示词收藏「粘贴拆分（可附图）」：只把图存到 workspace（不反推），返回 local_id/原图/缩略图。
export async function uploadPromptboxWorkspaceImage(
  files: File[],
): Promise<{ items: WorkspaceImageInfo[] }> {
  const fd = new FormData()
  for (const f of files) fd.append('files', f)
  const r = await fetch(`${base}/api/promptbox/workspace/image`, { method: 'POST', body: fd })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}
```

- [ ] **Step 4: PromptBoxPage 新增 import**

修改 `PromptBoxPage.vue` 顶部 import，把 `uploadPromptboxWorkspaceImage` 加入 `../api/client` 的导入：

```ts
import {
  splitPrompt, analyzePromptbox, savePromptbox, promptboxWorkspaceImageUrl,
  uploadPromptboxWorkspaceImage,
} from '../api/client'
```

- [ ] **Step 5: PromptBoxPage 新增状态与逻辑**

在 `PromptBoxPage.vue` `<script setup>` 中（现有 `doPasteSplit` 函数之后、`setCat` 之前）新增：

```ts
// 粘贴拆分（可附图）：独立于顶部 doPasteSplit（无图），这里可附图产带图项（不反推）
const pasteTextImg = ref('')
const pasteFile = ref<File | null>(null)
const pasteFileList = ref<any[]>([])
const pasteFileName = computed(() => pasteFile.value?.name || '')

function onPasteFileChange(opts: any) {
  const f = (opts.fileList || []).map((x: any) => x.file).filter(Boolean)[0] || null
  pasteFile.value = f
}

async function doPasteSplitWithImage() {
  const text = pasteTextImg.value.trim()
  if (!text) { msg.warning('请先输入提示词'); return }
  splitting.value = true
  try {
    let local_id = '', original = '', thumb = ''
    if (pasteFile.value) {
      const up = await uploadPromptboxWorkspaceImage([pasteFile.value])
      const m = up.items[0]
      local_id = m.local_id; original = m.original; thumb = m.thumb
    }
    const res = await splitPrompt(text)
    items.value = [...items.value, {
      local_id, original, thumb,
      categories: { ...emptyCats(), ...res.categories },
      extras: [...res.extras], raw_prompt: text,
    }]
    selectedIdx.value = items.value.length - 1
    pasteTextImg.value = ''
    pasteFile.value = null
    pasteFileList.value = []
    msg.success(local_id ? '已拆分（含图）' : '已拆分')
  } catch (e: any) { msg.error('拆分失败：' + e.message) }
  finally { splitting.value = false }
}
```

> `computed` 需在 vue import 中（当前 `import { ref, computed, onMounted, watch, h } from 'vue'` 已含 `computed`）。`splitting`、`emptyCats`、`items`、`selectedIdx`、`msg` 均已存在，复用。

- [ ] **Step 6: PromptBoxPage 模板——拆分编辑区改为左右两栏**

把模板中现有的「选中项拆分编辑」整块 `<n-card v-if="selected" title="拆分编辑（选中项）">...</n-card>`（含其内 `v-for` 分类编辑与「标题/复制/另存」按钮行）替换为下面的 `.edit-row` 结构——**右栏 `.edit-card` 内部内容原样保留**，仅外层包一层并新增左栏：

```html
    <!-- 粘贴拆分（可附图） + 拆分编辑（选中项） 同一行 -->
    <div class="edit-row">
      <n-card title="粘贴拆分（可附图）" class="paste-card">
        <n-input v-model:value="pasteTextImg" type="textarea" :rows="5"
                 placeholder="粘贴自己写好的提示词，逗号或换行分隔" />
        <n-upload multiple :default-upload="false" :show-file-list="false"
                  v-model:file-list="pasteFileList" @change="onPasteFileChange" accept="image/*">
          <n-button size="small">选择附图（可选）</n-button>
        </n-upload>
        <span v-if="pasteFileName" class="paste-file-name">{{ pasteFileName }}</span>
        <n-button :loading="splitting" type="primary" @click="doPasteSplitWithImage">粘贴拆分</n-button>
      </n-card>
      <n-card v-if="selected" title="拆分编辑（选中项）" class="edit-card">
        <div v-for="k in [...ORDER, 'extras']" :key="k" style="margin-top:8px">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:2px">
            <span style="font-size:13px">{{ TITLES[k] }}</span>
            <n-button size="tiny" @click="copyCat(k)">复制当前分类</n-button>
          </div>
          <n-dynamic-tags v-if="k !== 'extras'" :value="selected.categories[k] || []"
                          @update:value="(v: string[]) => setCat(k, v)" />
          <n-dynamic-tags v-else :value="selected.extras" @update:value="(v: string[]) => setExtras(v)" />
        </div>
        <div style="margin-top:12px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          <n-input v-model:value="title" placeholder="收藏标题（可选）" style="max-width:240px" />
          <n-button size="small" @click="copyPrompt">复制完整 prompt</n-button>
          <n-button size="small" type="primary" @click="saveAsCollection">另存为收藏</n-button>
        </div>
      </n-card>
    </div>
```

> 该块位于「工作区网格」`</div>`（或 `<n-empty>`）之后、`</n-space>` 之前。顶部「上传图片反推」卡片内的粘贴拆分（`pasteText`/`doPasteSplit`）**保持原样不动**。

- [ ] **Step 7: PromptBoxPage 样式**

在 `<style scoped>` 末尾追加：

```css
.edit-row { display: flex; gap: 16px; align-items: flex-start; flex-wrap: wrap }
.paste-card { width: 300px; flex-shrink: 0 }
.paste-card > :deep(.n-card__content) { display: flex; flex-direction: column; gap: 8px }
.paste-file-name { font-size: 12px; color: var(--cat-input-color, #888) }
.edit-card { flex: 1; min-width: 300px }
@media (max-width: 760px) { .paste-card, .edit-card { width: 100%; flex: 1 1 100% } }
```

- [ ] **Step 8: 运行测试确认通过**

Run: `cd wd14-tagger-web/frontend && npx vitest run src/__tests__/PromptBoxPage.test.ts`
Expected: PASS（全部用例：含新增 2 个 + 既有「粘贴提示词拆分」「上传反推另存」等回归用例）。

> 既有用例 `w.find('textarea')` 取第一个 textarea = 顶部 `pasteText`（模板顺序顶部在前），其「粘贴拆分」按钮 `findAll('button').find(...'粘贴拆分')` 取第一个 = 顶部按钮，均仍正确指向保留的顶部无图入口，不受新增左栏影响。

- [ ] **Step 9: 提交**

```bash
cd wd14-tagger-web
git add frontend/src/api/client.ts frontend/src/views/PromptBoxPage.vue frontend/src/__tests__/PromptBoxPage.test.ts
git commit -m "feat: 提示词收藏新增粘贴拆分（可附图）入口"
```

---

### Task 4: 构建 + 整合包同步

**Files:**
- Build: `wd14-tagger-web/frontend/dist`（产物）
- Sync: 两处整合包的 `frontend/dist` 与 `backend/api/routes_promptbox.py`

- [ ] **Step 1: 构建前端**

Run: `cd wd14-tagger-web/frontend && npm run build`
Expected: `vue-tsc -b` 类型检查通过、`vite build` 产出 `dist/`，无 TS 错误。

- [ ] **Step 2: 同步 dist 到两处整合包**

```bash
cp -r wd14-tagger-web/frontend/dist/* wd14-tagger-web/../WD14-Tagger-Web-Portable/wd14-tagger-web/frontend/dist/
cp -r wd14-tagger-web/frontend/dist/* /i/WD14-Tagger-Web-Portable/wd14-tagger-web/frontend/dist/
```

> 第一处整合包路径：`i:\trae\wd14\WD14-Tagger-Web-Portable\wd14-tagger-web\frontend\dist`；第二处：`I:\WD14-Tagger-Web-Portable\wd14-tagger-web\frontend\dist`。注意：若第一处整合包 `wd14-tagger-web` 为空目录（`pack_portable.py` 中间态），跳过该处并如实告知用户「等 pack 完再同步」，不要往空目录放孤立 dist。

- [ ] **Step 3: 同步后端 routes_promptbox.py 到两处整合包**

```bash
cp wd14-tagger-web/backend/api/routes_promptbox.py wd14-tagger-web/../WD14-Tagger-Web-Portable/wd14-tagger-web/backend/api/routes_promptbox.py
cp wd14-tagger-web/backend/api/routes_promptbox.py /i/WD14-Tagger-Web-Portable/wd14-tagger-web/backend/api/routes_promptbox.py
```

> 同样：第一处为空目录则跳过并告知。**只 cp 该单文件，绝不运行 `pack_portable.py`、绝不 `git add pack_portable.py`。**

- [ ] **Step 4: 提交 dist（仓库已跟踪 dist）**

```bash
cd wd14-tagger-web
git add frontend/dist
git commit -m "build: 同步前端 dist（收藏排序 + 粘贴拆分可附图）"
```

> 整合包目录在仓库外（独立 git/非 git），其同步不纳入本仓库 commit。

---

## Self-Review（计划自检）

**1. Spec 覆盖：**
- 需求1（排序）→ Task 1 ✓
- 需求2 后端端点 → Task 2 ✓
- 需求2 client 函数 → Task 3 Step 3 ✓
- 需求2 PromptBoxPage 卡片 + 逻辑 + 布局 → Task 3 Step 4-7 ✓
- 顶部无图粘贴拆分保留 → Global Constraints + Task 3 Step 8 备注 ✓
- 测试（前端 vitest）→ Task 1/3 ✓；后端无 pytest（遵循惯例，手动 curl）→ Task 2 Step 4 ✓
- 整合包同步（dist + routes_promptbox.py，不重新打包）→ Task 4 ✓

**2. 占位符扫描：** 无 TBD/TODO；每步含完整代码或确切命令。

**3. 类型一致性：**
- `WorkspaceImageInfo` 在 client.ts 定义（Task 3 Step 3），`uploadPromptboxWorkspaceImage` 返回 `{items: WorkspaceImageInfo[]}`（Step 3），`doPasteSplitWithImage` 取 `up.items[0].local_id/original/thumb`（Step 5）—— 字段一致 ✓
- `pasteTextImg`/`pasteFile`/`pasteFileList`/`pasteFileName` 定义（Step 5）与模板绑定（Step 6）一致 ✓
- 后端返回字段 `{local_id, original, thumb, width, height}`（Task 2）与 `WorkspaceImageInfo`（Task 3 Step 3）一致 ✓
