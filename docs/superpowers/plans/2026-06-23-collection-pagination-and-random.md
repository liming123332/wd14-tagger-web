# 收藏列表分页 + 随机页「提示词收藏」来源 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 `/collections` 提示词收藏列表加页码分页，并让随机抽取页（RandomPage）新增「提示词收藏」来源可随机抽收藏卡片。

**Architecture:** 纯前端改动，后端零改动。CollectionListPage 在已全量加载的 `filtered` 上做前端切片 + `NPagination`；RandomPage 扩展 `source` 增加 `'promptbox'`，`shuffle()` 调 `listPromptbox()` 后前端 Fisher-Yates 抽样，渲染精简收藏卡片。复用 RandomPage 现有竞争条件防御。

**Tech Stack:** Vue 3 SFC（`<script setup lang="ts">`）+ Naive UI + vitest / @vue/test-utils；构建 Vite（`npm run build`）。

## Global Constraints

- **简体中文 UI 文案**（标题、空态、按钮）。
- **执行前必须先建分支**：当前仓库处于 detached HEAD，先运行 `git switch -c feat-collection-pagination-random`，再开始 Task 1。
- **PAGE_SIZE = 30**（CollectionListPage 每页条数，固定值）。
- **收藏不足不重复**：promptbox 来源抽样数 < size 时只返回现有，不凑数。
- **复用 RandomPage 竞争条件防御**：切源（`onSource`）已 `items.value = []` 再 shuffle，新来源自动受益，不得破坏。
- **前端测试命令**：`cd frontend && npx vitest run src/__tests__/<file>.test.ts`（单文件）。
- **后端零改动**，不涉及后端测试或后端文件同步。

## File Structure

- Modify: `frontend/src/views/CollectionListPage.vue` — 加分页（page 状态 / totalPages / paged computed / watch 夹紧 / NPagination）。
- Modify: `frontend/src/__tests__/CollectionListPage.test.ts` — 增补分页测试。
- Modify: `frontend/src/views/RandomPage.vue` — 加 `promptbox` 来源（SOURCE_OPTIONS / pickRandom / shuffle 分支 / 渲染分支 / 空态）。
- Modify: `frontend/src/__tests__/RandomPage.test.ts` — 增补 promptbox 来源测试。
- Build: `frontend/dist`（Vite 产物）。
- Sync: 两处整合包的 `frontend/dist`（`i:\trae\wd14\WD14-Tagger-Web-Portable` 与 `I:\WD14-Tagger-Web-Portable`）。

---

### Task 1: CollectionListPage 页码分页

**Files:**
- Modify: `frontend/src/views/CollectionListPage.vue`
- Test: `frontend/src/__tests__/CollectionListPage.test.ts`

**Interfaces:**
- Consumes: `listPromptbox(): Promise<PromptboxItem[]>`（现有，不改）。
- Produces: 列表按 30 条/页切片渲染，底部 `NPagination` 翻页；搜索时回到第一页；条目减少时页码自动夹紧防越界。

- [ ] **Step 1: 写失败测试（追加到 `CollectionListPage.test.ts` 末尾 `describe` 块内）**

```ts
  it('超过 PAGE_SIZE 分页：默认第一页30条，翻页切片', async () => {
    const items = Array.from({ length: 75 }, (_, i) => ({
      id: `c${i}`, title: `收藏${i}`, raw_prompt: 'p', categories: {}, extras: [],
      image_names: [], created_at: '', updated_at: '',
    }))
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url === '/api/promptbox') return { ok: true, json: async () => items } as any
      return { ok: true, json: async () => ({}) } as any
    }))
    const w = mount(CollectionListPage, { global: { stubs: { NMenu: true } } })
    await flushPromises()
    // 默认 page=1：渲染 c0~c29，不渲染 c30
    expect(w.text()).toContain('收藏0')
    expect(w.text()).toContain('收藏29')
    expect(w.text()).not.toContain('收藏30')
    // 切到 page=2：渲染 c30~c59
    await w.findComponent({ name: 'Pagination' }).vm.$emit('update:page', 2)
    await flushPromises()
    expect(w.text()).toContain('收藏30')
    expect(w.text()).not.toContain('收藏0')
    // 切到 page=3：渲染 c60~c74（15条）
    await w.findComponent({ name: 'Pagination' }).vm.$emit('update:page', 3)
    await flushPromises()
    expect(w.text()).toContain('收藏74')
    expect(w.text()).not.toContain('收藏59')
  })

  it('搜索时回到第一页', async () => {
    const items = Array.from({ length: 75 }, (_, i) => ({
      id: `c${i}`, title: `收藏${i}`, raw_prompt: 'p', categories: {}, extras: [],
      image_names: [], created_at: '', updated_at: '',
    }))
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url === '/api/promptbox') return { ok: true, json: async () => items } as any
      return { ok: true, json: async () => ({}) } as any
    }))
    const w = mount(CollectionListPage, { global: { stubs: { NMenu: true } } })
    await flushPromises()
    // 先翻到 page=2
    await w.findComponent({ name: 'Pagination' }).vm.$emit('update:page', 2)
    await flushPromises()
    expect(w.text()).toContain('收藏30')
    // 搜索框输入 → page 重置回 1
    await w.find('input').setValue('收藏0')
    await flushPromises()
    expect(w.text()).toContain('收藏0')
    expect(w.text()).not.toContain('收藏30')
  })

  it('条数不超过 PAGE_SIZE 时不渲染分页器', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url === '/api/promptbox') {
        return { ok: true, json: async () => [
          { id: 'c1', title: 'a', raw_prompt: 'p', categories: {}, extras: [], image_names: [], created_at: '', updated_at: '' },
        ] } as any
      }
      return { ok: true, json: async () => ({}) } as any
    }))
    const w = mount(CollectionListPage, { global: { stubs: { NMenu: true } } })
    await flushPromises()
    expect(w.findComponent({ name: 'Pagination' }).exists()).toBe(false)
  })
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd frontend && npx vitest run src/__tests__/CollectionListPage.test.ts`
Expected: 3 个新测试 FAIL（`Pagination` 组件不存在 / `filtered` 未切片导致 c0~c74 全渲染）。

- [ ] **Step 3: 实现分页（修改 `CollectionListPage.vue`）**

3a. `import` 行修改——`vue` 加 `watch`，`naive-ui` 加 `NPagination`：

旧：
```ts
import { ref, computed, onMounted } from 'vue'
import {
  NGrid, NGridItem, NInput, NButton, NCard, NImage, NTag, NEmpty, NSpace, NPopconfirm, useMessage,
} from 'naive-ui'
```
新：
```ts
import { ref, computed, watch, onMounted } from 'vue'
import {
  NGrid, NGridItem, NInput, NButton, NCard, NImage, NTag, NEmpty, NSpace, NPopconfirm, NPagination, useMessage,
} from 'naive-ui'
```

3b. 在 `filtered` computed 之后、`catCount` 之前插入分页状态与切片：

```ts
// 分页：filtered 全量在内存，前端切片（收藏量级小，无需后端分页）
const PAGE_SIZE = 30
const page = ref(1)
const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / PAGE_SIZE)))
const paged = computed(() => {
  const start = (page.value - 1) * PAGE_SIZE
  return filtered.value.slice(start, start + PAGE_SIZE)
})
// 条目减少（删除后 reload）使 page 越界时夹紧到最后一页
watch(totalPages, (tp) => { if (page.value > tp) page.value = tp })
```

3c. 网格 `v-for` 由 `filtered` 改为 `paged`：

旧：
```html
  <n-grid v-else cols="2 600:3 900:4 1200:5" :x-gap="12" :y-gap="12">
    <n-grid-item v-for="it in filtered" :key="it.id">
```
新：
```html
  <n-grid v-else cols="2 600:3 900:4 1200:5" :x-gap="12" :y-gap="12">
    <n-grid-item v-for="it in paged" :key="it.id">
```

3d. 搜索框 `@update:value` 增加 `page = 1`：

旧：
```html
        <n-input :value="keyword" placeholder="搜索标题或提示词" size="small" clearable
                 @update:value="(v: string) => keyword = v"
                 style="min-width:240px;max-width:360px" /></div>
```
新：
```html
        <n-input :value="keyword" placeholder="搜索标题或提示词" size="small" clearable
                 @update:value="(v: string) => { keyword = v; page = 1 }"
                 style="min-width:240px;max-width:360px" /></div>
```

3e. 在 `</n-grid>` 之后、`</template>` 之前插入分页器：

```html
  </n-grid>
  <div v-if="filtered.length > PAGE_SIZE" style="display:flex;justify-content:center;margin-top:16px">
    <n-pagination :page="page" :item-count="filtered.length" :page-size="PAGE_SIZE"
                  @update:page="(p: number) => page = p" />
  </div>
</template>
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd frontend && npx vitest run src/__tests__/CollectionListPage.test.ts`
Expected: 全部 PASS（含 3 个新分页测试 + 原有测试）。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/CollectionListPage.vue frontend/src/__tests__/CollectionListPage.test.ts
git commit -m "feat: 收藏列表页码分页（每页30，搜索回首页，越界夹紧）"
```

---

### Task 2: RandomPage 新增「提示词收藏」来源

**Files:**
- Modify: `frontend/src/views/RandomPage.vue`
- Test: `frontend/src/__tests__/RandomPage.test.ts`

**Interfaces:**
- Consumes: `listPromptbox(): Promise<PromptboxItem[]>`、`promptboxImageUrl(id, name): string`（client.ts 现有）。
- Produces: RandomPage `source` 增加 `'promptbox'`；选中时隐藏 cfSource 下拉，`shuffle()` 从收藏前端抽样（不足不重复），渲染精简收藏卡片，点击跳 `/collections/:id`。

- [ ] **Step 1: 写失败测试（修改 `RandomPage.test.ts` 的 client mock + 追加用例）**

1a. 在文件顶部 `vi.mock('../api/client', ...)` 块内，给返回对象追加 `listPromptbox`（保留现有 `...actual` 与 `randomImages` override）：

旧（mock 返回对象片段）：
```ts
  return {
    ...actual,
    randomImages: vi.fn(async () => {
      // 真实图库 item 结构（见 api/client.ts 的 randomImages）：{id, source_name, tags, ...}，
      // 【没有 entry_key】。故意不伪造 entry_key——切源瞬间 source 已变、items 仍是图库 item
      // 的那一帧，若代码未防御，cardTo→parseEntryKey(undefined) 会在“切源不崩”用例里暴露崩溃。
      calls.push('randomImages'); return { items: [{ id: 'g1', source_name: 'g', tags: [] }] }
    }),
  }
```
新（追加 `listPromptbox`）：
```ts
  return {
    ...actual,
    randomImages: vi.fn(async () => {
      // 真实图库 item 结构（见 api/client.ts 的 randomImages）：{id, source_name, tags, ...}，
      // 【没有 entry_key】。故意不伪造 entry_key——切源瞬间 source 已变、items 仍是图库 item
      // 的那一帧，若代码未防御，cardTo→parseEntryKey(undefined) 会在“切源不崩”用例里暴露崩溃。
      calls.push('randomImages'); return { items: [{ id: 'g1', source_name: 'g', tags: [] }] }
    }),
    listPromptbox: vi.fn(async () => {
      calls.push('listPromptbox')
      return [
        { id: 'p1', title: '收藏甲', raw_prompt: 'a, b', categories: {}, extras: [], image_names: [], created_at: '', updated_at: '' },
        { id: 'p2', title: '收藏乙', raw_prompt: 'c, d', categories: {}, extras: [], image_names: [], created_at: '', updated_at: '' },
      ]
    }),
  }
```

1b. 在 `describe` 块末尾追加用例：

```ts
  it('切到 promptbox 调 listPromptbox，不调 randomImages/randomCf', async () => {
    const w = mount(RandomPage); await flushPromises()
    calls.length = 0
    const selects = w.findAllComponents({ name: 'Select' })
    await selects[0].vm.$emit('update:value', 'promptbox')
    await flushPromises()
    expect(calls).toContain('listPromptbox')
    expect(calls.some(c => c === 'randomImages')).toBe(false)
    expect(calls.some(c => c.startsWith('randomCf:'))).toBe(false)
  })

  it('promptbox 来源渲染收藏卡片标题', async () => {
    const w = mount(RandomPage); await flushPromises()
    const selects = w.findAllComponents({ name: 'Select' })
    await selects[0].vm.$emit('update:value', 'promptbox')
    await flushPromises()
    expect(w.text()).toContain('收藏甲')
    expect(w.text()).toContain('收藏乙')
  })

  it('promptbox 切源不崩（竞态：source 已变、items 异步替换的中间帧）', async () => {
    const w = mount(RandomPage); await flushPromises()
    const selects = w.findAllComponents({ name: 'Select' })
    await selects[0].vm.$emit('update:value', 'promptbox')
    await flushPromises()
    expect(calls.some(c => c === 'listPromptbox')).toBe(true)
  })
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd frontend && npx vitest run src/__tests__/RandomPage.test.ts`
Expected: 3 个新测试 FAIL（切到 `promptbox` 不触发 `listPromptbox` / 不渲染收藏标题）。

- [ ] **Step 3: 实现 promptbox 来源（修改 `RandomPage.vue`）**

3a. `import` 修改——`client` 加 `listPromptbox, promptboxImageUrl`，并加 `useRouter`：

旧：
```ts
import { ref, onMounted } from 'vue'
import { NGrid, NGridItem, NEmpty, NButton, NSelect } from 'naive-ui'
import { randomImages } from '../api/client'
```
新：
```ts
import { ref, onMounted } from 'vue'
import { NGrid, NGridItem, NEmpty, NButton, NSelect, NCard, NImage } from 'naive-ui'
import { useRouter } from 'vue-router'
import { randomImages, listPromptbox, promptboxImageUrl } from '../api/client'
```

3b. 在 `import ImageCard ...` 之后加 `const router = useRouter()`：

旧：
```ts
import ImageCard from '../components/ImageCard.vue'

const items = ref<any[]>([])
```
新：
```ts
import ImageCard from '../components/ImageCard.vue'

const router = useRouter()
const items = ref<any[]>([])
```

3c. `source` 类型扩展 + `SOURCE_OPTIONS` 追加 promptbox：

旧：
```ts
const source = ref<'gallery' | 'characters' | 'artists'>('gallery')
const cfSource = ref<'danbooru' | 'anima'>('anima')

const SOURCE_OPTIONS = [
  { label: '图库', value: 'gallery' },
  { label: '角色图鉴', value: 'characters' },
  { label: '艺术家', value: 'artists' },
]
```
新：
```ts
const source = ref<'gallery' | 'characters' | 'artists' | 'promptbox'>('gallery')
const cfSource = ref<'danbooru' | 'anima'>('anima')

const SOURCE_OPTIONS = [
  { label: '图库', value: 'gallery' },
  { label: '角色图鉴', value: 'characters' },
  { label: '艺术家', value: 'artists' },
  { label: '提示词收藏', value: 'promptbox' },
]
```

3d. 在 `shuffle` 之前加 `pickRandom` 工具函数：

```ts
// 前端随机抽样：Fisher-Yates 洗牌取前 n（不足取全部，不重复）
function pickRandom<T>(arr: T[], n: number): T[] {
  const a = [...arr]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a.slice(0, Math.min(n, a.length))
}
```

3e. `shuffle` 增加 promptbox 分支：

旧：
```ts
async function shuffle() {
  loading.value = true
  try {
    if (source.value === 'gallery') {
      items.value = (await randomImages(size)).items
    } else {
      const type = source.value === 'characters' ? 'characters' : 'artists'
      items.value = (await randomCf(type, cfSource.value, size)).items
    }
  } finally {
    loading.value = false
  }
}
```
新：
```ts
async function shuffle() {
  loading.value = true
  try {
    if (source.value === 'gallery') {
      items.value = (await randomImages(size)).items
    } else if (source.value === 'promptbox') {
      items.value = pickRandom(await listPromptbox(), size)
    } else {
      const type = source.value === 'characters' ? 'characters' : 'artists'
      items.value = (await randomCf(type, cfSource.value, size)).items
    }
  } finally {
    loading.value = false
  }
}
```

3f. `onSource` 已有 `items.value = []` + `shuffle()`，无需改动（promptbox 自动受益）。

3g. template 中 cfSource 下拉显隐条件修改（promptbox 不分数据源）：

旧：
```html
      <n-select v-if="source !== 'gallery'" :value="cfSource" :options="CF_SOURCE_OPTIONS" size="small"
                style="width:130px" @update:value="onCfSource" />
```
新：
```html
      <n-select v-if="source !== 'gallery' && source !== 'promptbox'" :value="cfSource" :options="CF_SOURCE_OPTIONS" size="small"
                style="width:130px" @update:value="onCfSource" />
```

3h. 空态 `description` 追加 promptbox 文案：

旧：
```html
  <n-empty v-if="!items.length" :description="source === 'gallery' ? '图库还没有图片，先去上传' : '暂无随机项'" />
```
新：
```html
  <n-empty v-if="!items.length" :description="source === 'gallery' ? '图库还没有图片，先去上传' : source === 'promptbox' ? '还没有提示词收藏，去提示词收藏页创建' : '暂无随机项'" />
```

3i. 网格内渲染分支：`n-grid-item` 内增加 promptbox 卡片，gallery 改 `v-else-if`：

旧：
```html
    <n-grid-item v-for="it in items" :key="(it.entry_key as string) ?? (it.id as string)">
      <ImageCard v-if="source === 'gallery'" :item="it" />
      <ImageCard v-else :item="it" :to="cardTo(it)" :img-src="cardImg(it)"
                 :title-text="it.name || ''" :tags-list="cardTags(it)"
                 :favorite="it.favorite" @toggle-favorite="onToggleFav(it)" />
    </n-grid-item>
```
新：
```html
    <n-grid-item v-for="it in items" :key="(it.entry_key as string) ?? (it.id as string)">
      <n-card v-if="source === 'promptbox'" size="small" hoverable
              @click="router.push(`/collections/${it.id}`)" style="cursor:pointer">
        <div class="pb-title">{{ it.title || '(未命名)' }}</div>
        <n-image v-if="it.image_names && it.image_names.length" width="100%" object-fit="cover"
                 preview-disabled :src="promptboxImageUrl(it.id, it.image_names[0])" />
        <div class="pb-prompt">{{ it.raw_prompt || '(无提示词)' }}</div>
      </n-card>
      <ImageCard v-else-if="source === 'gallery'" :item="it" />
      <ImageCard v-else :item="it" :to="cardTo(it)" :img-src="cardImg(it)"
                 :title-text="it.name || ''" :tags-list="cardTags(it)"
                 :favorite="it.favorite" @toggle-favorite="onToggleFav(it)" />
    </n-grid-item>
```

3j. `<style scoped>` 末尾追加 promptbox 卡片样式：

```css
.pb-title { font-size: 13px; font-weight: 600 }
.pb-prompt {
  font-size: 12px; color: var(--cat-input-color, #666); margin-top: 6px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd frontend && npx vitest run src/__tests__/RandomPage.test.ts`
Expected: 全部 PASS（含 3 个新 promptbox 测试 + 原有源切换/竞态测试）。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/RandomPage.vue frontend/src/__tests__/RandomPage.test.ts
git commit -m "feat: 随机页新增提示词收藏来源（前端抽样，不足不重复）"
```

---

### Task 3: 前端构建 + 整合包同步 + 手动验证

**Files:**
- Build: `frontend/dist`
- Sync: 两处整合包 `frontend/dist`

**注意：** 此任务为构建与部署，不产生源码 commit（dist 是构建产物）。夹紧 watch（删除场景）在此任务手动验证。

- [ ] **Step 1: 构建前端**

Run: `cd frontend && npm run build`
Expected: 构建成功，`frontend/dist/assets/` 生成新的 `index-*.js`（hash 与构建前不同）。

- [ ] **Step 2: 同步 dist 到两处整合包**

Run（bash）：
```bash
SRC=/i/trae/wd14/wd14-tagger-web/frontend/dist
for PKG in "/i/trae/wd14/WD14-Tagger-Web-Portable" "/i/WD14-Tagger-Web-Portable"; do
  DST="$PKG/wd14-tagger-web/frontend/dist"
  rm -rf "$DST" && cp -r "$SRC" "$DST" && echo "synced -> $PKG"
  ls "$DST/assets/"
done
```
Expected: 两处整合包 `frontend/dist/assets/` 的 `index-*.js` hash 与源码 dist 一致。

- [ ] **Step 3: 手动验证（起服务 + 浏览器）**

启动整合包或源码服务后，在浏览器验证：
1. `/collections`：收藏 >30 条时底部出现页码，翻页切片正确；搜索后回到第一页；删除某条后若当前页越界，自动夹紧到最后一页。
2. `/random`：来源下拉选「提示词收藏」→ cfSource 下拉消失 → 「再抽一页」随机抽收藏卡片（标题/缩略图/prompt），点击跳 `/collections/:id`；收藏 <24 时只显示现有数量、无重复；从其他来源切到提示词收藏不报 `split` 错误。

验证通过即完成。

---

## Self-Review

**1. Spec coverage:**
- 需求1（/collections 分页，页码方式，前端切片）→ Task 1 ✓
- 需求2（RandomPage 加提示词收藏来源）→ Task 2 ✓
- 收藏不足不重复 → Task 2 `pickRandom`（Step 3d）+ 测试（Step 1 渲染2条不重复）✓
- 复用竞争条件防御 → Task 2 Step 3f（onSource 不改）+ 竞态测试 ✓
- 整合包同步 → Task 3 ✓
- 后端零改动 → 全计划无后端任务 ✓

**2. Placeholder scan:** 无 TBD/TODO；所有 step 含完整代码或确切命令。✓

**3. Type consistency:**
- `source` 类型 `'gallery'|'characters'|'artists'|'promptbox'` 在 Task 2 定义（3c）并被 `shuffle`（3e）/ template（3g,3h,3i）一致使用 ✓
- `pickRandom<T>` 定义（3d）与 `shuffle` 调用（`pickRandom(await listPromptbox(), size)`）签名一致 ✓
- `listPromptbox` 返回 `PromptboxItem[]`，promptbox 卡片用 `it.id`/`it.title`/`it.image_names`/`it.raw_prompt` 均为 `PromptboxItem` 字段 ✓
- 测试中 `findComponent({ name: 'Pagination' })` 对应 Naive UI `NPagination`（Task 1 Step 3a 引入）✓
- 测试中 `findComponent({ name: 'Select' })` 对应现有 `NSelect`（RandomPage 已用）✓

无问题。
