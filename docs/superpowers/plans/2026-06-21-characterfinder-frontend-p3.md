# Character Finder P3 前端接入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 接入 P1 Task 11 已就绪的后端 `favorites` / `recent` / `random` 端点，前端提供 RandomPage 源切换（图库/角色/艺术家）、cf 收藏夹独立页、列表页最近查看区。

**Architecture:** 纯前端增量。4 处改动 + 1 个新视图：(1) `characterfinder.ts` 补 3 个只读 async 函数；(2) `RandomPage.vue` 加源切换复用三个数据源；(3) 新视图 `CfFavoritesPage.vue` 消费 `favorites`；(4) `CharactersPage` / `ArtistsPage` 顶部加最近查看横向区；(5) `router.ts` + `App.vue` + `icons.ts` 接线。全部复用 P2 的 ImageCard 通用化 props、parseEntryKey（对象解构）、cfAssetUrl、列表页 filter-bar/n-grid 视觉。

**Tech Stack:** Vue 3.5.34 (`<script setup lang="ts">`) · naive-ui 2.44.1 · vue-router 4.6.4 · TypeScript 6.0.2 · vite 8.0.12。测试 vitest ^4.1.9 + @vue/test-utils ^2.4.11 + jsdom。

## Global Constraints

- **无新增 npm 依赖**：全用现有 vue / naive-ui / vue-router / vitest 栈。
- **后端不动**：P1 已 master（231 passed），P3 只读消费 favorites/recent/random，不改任何 `backend/` 文件。
- **锁定语义延续**：P3 只读消费端点，不碰 `locked_tags`；P2 三重保险（`CfSaveBody` 无 `locked_tags` / `buildPromptWithLocked` 前置 / 详情页只读锁区）不受影响。本阶段不写任何 save/tag 调用。
- **类型一致**：复用 P2 的 `CfListItem` / `parseEntryKey`（对象解构 `{kind,source,key}`）/ `cfAssetUrl` / ImageCard props。
- **API 客户端风格**：`const base = ''` + 原生 fetch + URLSearchParams 编 query + `.then(r => r.json())`。CfListItem 角色 item 含 `entry_key/source/name/core_tags/favorite/thumb_url`；艺术家 item 含 `entry_key/source/name/tag/thumb1_url/thumb2_url/favorite`。
- **router import 带 `.vue` 后缀**（漏 → vue-tsc TS2307）。
- **App.vue router-view 外层 `<div :key="route.path" class="route-view">` 包装不动**（Transition out-in + 非 element 根节点修复）。
- **parseEntryKey 返回对象 `{kind,source,key}`**，列表态用 `const { source: s, key } = parseEntryKey(...)` 对象解构（数组解构会运行时崩）。
- **测试命令**：`cd frontend && npx vitest run`（全量回归，P2 基线 160 passed / 27 文件）+ `cd frontend && npm run build`（vue-tsc，0 exit）。单个文件：`cd frontend && npx vitest run src/__tests__/<file>.test.ts`。
- **基线分支**：`feat/characterfinder-p3`，base=`master`（d403545）。当前 HEAD 含 P3 spec commit (8787f12)。

---

## File Structure

| 文件 | 动作 | 职责 |
|---|---|---|
| `frontend/src/api/characterfinder.ts` | Modify（末尾追加） | 补 `listCfFavorites` / `listCfRecent` / `randomCf` 三个只读 async 函数 |
| `frontend/src/__tests__/characterfinder.test.ts` | Modify | 3 函数 URL 构造断言 |
| `frontend/src/components/icons.ts` | Modify（末尾追加） | 新增 `IconBookmark` |
| `frontend/src/__tests__/icons.test.ts` | Modify | `IconBookmark` 渲染断言 |
| `frontend/src/views/RandomPage.vue` | Modify（重写 `<script setup>` + `<template>`） | 源切换：图库/角色图鉴/艺术家 |
| `frontend/src/__tests__/RandomPage.test.ts` | Modify / Create | 源切换触发不同 API |
| `frontend/src/views/CfFavoritesPage.vue` | Create | cf 收藏夹独立页（角色/艺术家 tab + 前端搜索 + 乐观移除） |
| `frontend/src/__tests__/CfFavoritesPage.test.ts` | Create | tab 切换 / 渲染 / 乐观移除 / 搜索 |
| `frontend/src/views/CharactersPage.vue` | Modify | 顶部加最近查看横向区 |
| `frontend/src/views/ArtistsPage.vue` | Modify | 顶部加最近查看横向区 |
| `frontend/src/__tests__/CharactersPage.test.ts` | Modify | recent 渲染 / 空隐藏 |
| `frontend/src/__tests__/ArtistsPage.test.ts` | Modify | recent 渲染 / 空隐藏 |
| `frontend/src/router.ts` | Modify | 注册 `/cf/favorites` 路由 |
| `frontend/src/App.vue` | Modify | icon import + ITEMS 加「cf 收藏」 |
| `frontend/src/__tests__/router.test.ts` | Modify | `/cf/favorites` 路径注册断言 |

---

### Task 1: cf API 扩展（favorites / recent / random）

**Files:**
- Modify: `frontend/src/api/characterfinder.ts`（末尾追加，在 `toggleArtistFavorite` 之后）
- Test: `frontend/src/__tests__/characterfinder.test.ts`

**Interfaces:**
- Consumes: 无（P1 后端端点已就绪）
- Produces:
  ```ts
  listCfFavorites(kind: 'char' | 'artist'): Promise<{ items: CfListItem[] }>
  listCfRecent(kind: 'char' | 'artist', limit?: number): Promise<{ items: CfListItem[] }>   // limit 默认 50
  randomCf(type: 'characters' | 'artists', source: string, size?: number): Promise<{ items: CfListItem[] }>  // size 默认 24
  ```
  Task 3 (RandomPage)、Task 4 (CfFavoritesPage)、Task 5 (列表页最近查看) 均依赖这三个函数名与签名。

- [ ] **Step 1: Write the failing test**

在 `frontend/src/__tests__/characterfinder.test.ts` 顶部 import 块追加三个函数名：

```ts
import {
  parseEntryKey, cfAssetUrl,
  searchCharacters, listCharacterSeries, getCharacter,
  tagCharacter, reclassifyCharacter, saveCharacter,
  uploadCharacterImage, toggleCharacterFavorite,
  searchArtists, getArtist, tagArtist, reclassifyArtist, saveArtist,
  uploadArtistImage, toggleArtistFavorite,
  listCfFavorites, listCfRecent, randomCf,
} from '../api/characterfinder'
```

在文件末尾追加新 describe 块（仿现有 `searchCharacters` 测试的 fetch stub + URL 断言风格）：

```ts
describe('cf favorites/recent/random', () => {
  beforeEach(() => vi.unstubAllGlobals())
  it('listCfFavorites GET /api/cf/favorites?kind=', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url); return { ok: true, json: async () => ({ items: [] }) } as any
    }))
    await listCfFavorites('artist')
    expect(urls[0]).toContain('/api/cf/favorites?kind=artist')
  })
  it('listCfRecent GET /api/cf/recent?kind=&limit=', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url); return { ok: true, json: async () => ({ items: [] }) } as any
    }))
    await listCfRecent('char', 10)
    expect(urls[0]).toContain('/api/cf/recent?kind=char')
    expect(urls[0]).toContain('limit=10')
  })
  it('listCfRecent 默认 limit=50', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url); return { ok: true, json: async () => ({ items: [] }) } as any
    }))
    await listCfRecent('char')
    expect(urls[0]).toContain('limit=50')
  })
  it('randomCf GET /api/cf/random?type=&source=&size=', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url); return { ok: true, json: async () => ({ items: [] }) } as any
    }))
    await randomCf('artists', 'anima', 12)
    expect(urls[0]).toContain('/api/cf/random?type=artists')
    expect(urls[0]).toContain('source=anima')
    expect(urls[0]).toContain('size=12')
  })
  it('randomCf 默认 size=24', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url); return { ok: true, json: async () => ({ items: [] }) } as any
    }))
    await randomCf('characters', 'danbooru')
    expect(urls[0]).toContain('size=24')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/__tests__/characterfinder.test.ts`
Expected: FAIL — `listCfFavorites is not defined` / import 解析失败（函数尚未导出）。

- [ ] **Step 3: Write minimal implementation**

在 `frontend/src/api/characterfinder.ts` 末尾（`toggleArtistFavorite` 函数之后）追加：

```ts

// ===== 收藏 / 最近 / 随机（消费 P1 Task 11 只读端点）=====
export async function listCfFavorites(kind: 'char' | 'artist'): Promise<{ items: CfListItem[] }> {
  return fetch(`${base}/api/cf/favorites?kind=${encodeURIComponent(kind)}`).then(r => r.json())
}

export async function listCfRecent(kind: 'char' | 'artist', limit = 50): Promise<{ items: CfListItem[] }> {
  const q = new URLSearchParams({ kind, limit: String(limit) })
  return fetch(`${base}/api/cf/recent?${q}`).then(r => r.json())
}

export async function randomCf(type: 'characters' | 'artists', source: string, size = 24): Promise<{ items: CfListItem[] }> {
  const q = new URLSearchParams({ type, source, size: String(size) })
  return fetch(`${base}/api/cf/random?${q}`).then(r => r.json())
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/__tests__/characterfinder.test.ts`
Expected: PASS（含新增 5 个 case + 原 parseEntryKey/cfAssetUrl/searchCharacters 等）。

- [ ] **Step 5: Commit**

```bash
cd frontend && npx vitest run src/__tests__/characterfinder.test.ts
git add frontend/src/api/characterfinder.ts frontend/src/__tests__/characterfinder.test.ts
git commit -m "feat(cf): add listCfFavorites/listCfRecent/randomCf api (P3 Task 1)"
```

---

### Task 2: IconBookmark 图标

**Files:**
- Modify: `frontend/src/components/icons.ts`（末尾追加）
- Test: `frontend/src/__tests__/icons.test.ts`

**Interfaces:**
- Consumes: 现有 `I(() => [h(...)])` 范式（见 `IconCharacter` / `IconArtist`）
- Produces: `IconBookmark: FunctionalComponent`（Task 6 App.vue 菜单图标用）

- [ ] **Step 1: Write the failing test**

在 `frontend/src/__tests__/icons.test.ts` 的 import 块追加 `IconBookmark`：

```ts
import {
  IconUpload, IconGallery, IconCheck, IconCopy, IconDownload,
  IconSun, IconMoon, IconMonitor,
  IconCharacter, IconArtist, IconBookmark,
} from '../components/icons'
```

把第一个 `it.each` 的表追加一行 `['IconBookmark', IconBookmark]`：

```ts
  it.each([
    ['IconUpload', IconUpload], ['IconGallery', IconGallery],
    ['IconCheck', IconCheck], ['IconCopy', IconCopy], ['IconDownload', IconDownload],
    ['IconBookmark', IconBookmark],
  ])('%s 渲染一个 svg', (_name, I) => {
    expect(wrap(I).find('svg').exists()).toBe(true)
  })
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/__tests__/icons.test.ts`
Expected: FAIL — `IconBookmark` 未导出（import 解析失败 / 表驱动 case 找不到组件）。

- [ ] **Step 3: Write minimal implementation**

在 `frontend/src/components/icons.ts` 末尾（`IconArtist` 之后）追加（书签轮廓，仿现有 `I(() => [h(...)])` 范式）：

```ts
export const IconBookmark = I(() => [
  h('path', { d: 'M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z' }),
])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/__tests__/icons.test.ts`
Expected: PASS（含新增 IconBookmark case）。

- [ ] **Step 5: Commit**

```bash
cd frontend && npx vitest run src/__tests__/icons.test.ts
git add frontend/src/components/icons.ts frontend/src/__tests__/icons.test.ts
git commit -m "feat(cf): add IconBookmark icon (P3 Task 2)"
```

---

### Task 3: RandomPage 源切换

**Files:**
- Modify: `frontend/src/views/RandomPage.vue`（重写 `<script setup>` + `<template>`）
- Test: `frontend/src/__tests__/RandomPage.test.ts`（若已存在则替换/追加其中 RandomPage 测试；不存在则新建）

**Interfaces:**
- Consumes:
  - `randomImages(size=24)` from `../api/client` → `{ items }`（图库 item，ImageCard 默认 props 回退）
  - `randomCf(type, source, size=24)` from Task 1 → `{ items: CfListItem[] }`
  - `toggleCharacterFavorite(source, key)` / `toggleArtistFavorite(source, key)` from P2 → `{ favorite }`
  - `parseEntryKey(ek) → { kind, source, key }` from P2（对象解构）
  - `ImageCard` props：`item / to? / imgSrc? / titleText? / tagsList? / favorite? / @toggle-favorite`
- Produces: `RandomPage` 默认导出（路由 `/random` 已注册，Task 6 不动此路由）

**设计要点**：
- `source: 'gallery' | 'characters' | 'artists'`（默认 `'gallery'`）；`cfSource: 'danbooru' | 'anima'`（默认 `'danbooru'`）。
- `shuffle()` 按 source 分发：gallery→`randomImages(size)`；characters→`randomCf('characters', cfSource, size)`；artists→`randomCf('artists', cfSource, size)`。
- 切源 / 切 cfSource 自动重抽。cfSource 下拉仅当 source≠gallery 时显示。
- gallery 卡片用 `<ImageCard :item="it" />`（默认）；cf 卡片用覆盖 props（to/imgSrc/titleText/tagsList/favorite + @toggle-favorite）。
- toggle 仅切换图标（随机页不从列表移除——与收藏列表语义不同）。

- [ ] **Step 1: Write the failing test**

`frontend/src/__tests__/RandomPage.test.ts`（若已存在，替换其中 RandomPage 相关 describe；保留文件其他无关测试）：

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import RandomPage from '../views/RandomPage.vue'

// mock 三个数据源 + 两个 toggle，记录调用以便断言源切换分发
const calls: string[] = []
vi.mock('../api/client', () => ({
  randomImages: vi.fn(async () => {
    calls.push('randomImages'); return { items: [{ id: 'g1', source_name: 'g', tags: [] }] }
  }),
}))
vi.mock('../api/characterfinder', () => ({
  randomCf: vi.fn(async (_t: string, _s: string) => {
    calls.push(`randomCf:${_t}:${_s}`); return { items: [{ entry_key: 'char:danbooru:k1', source: 'danbooru', name: 'n', favorite: false }] }
  }),
  toggleCharacterFavorite: vi.fn(async () => { calls.push('toggleChar'); return { favorite: true } }),
  toggleArtistFavorite: vi.fn(async () => { calls.push('toggleArtist'); return { favorite: true } }),
  parseEntryKey: (ek: string) => {
    const p = ek.split(':'); return { kind: p[0], source: p[1], key: p.slice(2).join(':') }
  },
}))

describe('RandomPage 源切换', () => {
  beforeEach(() => { calls.length = 0; vi.clearAllMocks() })

  it('默认 source=gallery 调 randomImages', async () => {
    mount(RandomPage); await flushPromises()
    expect(calls).toContain('randomImages')
    expect(calls.some(c => c.startsWith('randomCf:'))).toBe(false)
  })

  it('切到 characters 调 randomCf("characters", cfSource)', async () => {
    const w = mount(RandomPage); await flushPromises()
    calls.length = 0
    // 源下拉是第一个 NSelect；NSelect v-model:value 经 @update:value 触发
    const selects = w.findAllComponents({ name: 'NSelect' })
    await selects[0].vm.$emit('update:value', 'characters')
    await flushPromises()
    expect(calls.some(c => c === 'randomCf:characters:danbooru')).toBe(true)
  })

  it('切到 artists 调 randomCf("artists", cfSource)', async () => {
    const w = mount(RandomPage); await flushPromises()
    calls.length = 0
    const selects = w.findAllComponents({ name: 'NSelect' })
    await selects[0].vm.$emit('update:value', 'artists')
    await flushPromises()
    expect(calls.some(c => c === 'randomCf:artists:danbooru')).toBe(true)
  })

  it('角色源下切 cfSource=anima 重抽 randomCf characters anima', async () => {
    const w = mount(RandomPage); await flushPromises()
    // 切到 characters，cfSource 下拉才会渲染
    let selects = w.findAllComponents({ name: 'NSelect' })
    await selects[0].vm.$emit('update:value', 'characters'); await flushPromises()
    calls.length = 0
    // 切源后必须重新获取组件列表：v-if 渲染出的 cfSource 下拉不在旧数组里
    selects = w.findAllComponents({ name: 'NSelect' })
    await selects[1].vm.$emit('update:value', 'anima')
    await flushPromises()
    expect(calls.some(c => c === 'randomCf:characters:anima')).toBe(true)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/__tests__/RandomPage.test.ts`
Expected: FAIL — 当前 RandomPage 无源下拉，`findAllComponents({name:'NSelect'})` 为空 / 不调 randomCf。

- [ ] **Step 3: Write minimal implementation**

将 `frontend/src/views/RandomPage.vue` 整体替换为：

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NGrid, NGridItem, NEmpty, NButton, NSelect } from 'naive-ui'
import { randomImages } from '../api/client'
import {
  randomCf, toggleCharacterFavorite, toggleArtistFavorite, parseEntryKey,
  type CfListItem,
} from '../api/characterfinder'
import { IconRandom } from '../components/icons'
import ImageCard from '../components/ImageCard.vue'

const items = ref<any[]>([])
const size = 24
const loading = ref(false)

const source = ref<'gallery' | 'characters' | 'artists'>('gallery')
const cfSource = ref<'danbooru' | 'anima'>('danbooru')

const SOURCE_OPTIONS = [
  { label: '图库', value: 'gallery' },
  { label: '角色图鉴', value: 'characters' },
  { label: '艺术家', value: 'artists' },
]
const CF_SOURCE_OPTIONS = [
  { label: 'Danbooru', value: 'danbooru' },
  { label: 'Anima', value: 'anima' },
]

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
onMounted(shuffle)

function onSource(v: 'gallery' | 'characters' | 'artists') { source.value = v; shuffle() }
function onCfSource(v: 'danbooru' | 'anima') { cfSource.value = v; shuffle() }

// cf 卡片映射（gallery 用 ImageCard 默认 props，不走这些函数）
function cardTo(it: CfListItem): string {
  const { source: s, key } = parseEntryKey(it.entry_key)
  return source.value === 'artists' ? `/artists/${s}/${encodeURIComponent(key)}` : `/characters/${s}/${encodeURIComponent(key)}`
}
function cardImg(it: CfListItem): string {
  return source.value === 'artists' ? (it.thumb1_url || '') : (it.thumb_url || '')
}
function cardTags(it: CfListItem): string[] {
  const raw = source.value === 'artists' ? (it.tag || '') : (it.core_tags || '')
  return raw.split(',').map(t => t.trim()).filter(Boolean)
}
async function onToggleFav(it: CfListItem) {
  const { source: s, key } = parseEntryKey(it.entry_key)
  try {
    const r = source.value === 'artists'
      ? await toggleArtistFavorite(s, key)
      : await toggleCharacterFavorite(s, key)
    it.favorite = r.favorite
  } catch { /* 静默：随机页不弹错 */ }
}
</script>

<template>
  <div class="bar">
    <div class="field">
      <span class="field-label">来源</span>
      <n-select :value="source" :options="SOURCE_OPTIONS" size="small" style="width:140px" @update:value="onSource" />
      <n-select v-if="source !== 'gallery'" :value="cfSource" :options="CF_SOURCE_OPTIONS" size="small"
                style="width:130px" @update:value="onCfSource" />
    </div>
    <n-button type="primary" size="small" :loading="loading" @click="shuffle"><IconRandom/> 再抽一页</n-button>
  </div>
  <n-empty v-if="!items.length" :description="source === 'gallery' ? '图库还没有图片，先去上传' : '暂无随机项'" />
  <n-grid v-else cols="2 600:3 900:5 1200:6" :x-gap="12" :y-gap="12">
    <n-grid-item v-for="it in items" :key="(it.entry_key as string) ?? (it.id as string)">
      <ImageCard v-if="source === 'gallery'" :item="it" />
      <ImageCard v-else :item="it" :to="cardTo(it)" :img-src="cardImg(it)"
                 :title-text="it.name || ''" :tags-list="cardTags(it)"
                 :favorite="it.favorite" @toggle-favorite="onToggleFav(it)" />
    </n-grid-item>
  </n-grid>
</template>

<style scoped>
.bar { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; flex-wrap: wrap }
.field { display: flex; align-items: center; gap: 8px }
.field-label { font-size: 13px; font-weight: 600; color: var(--n-text-color-3, #6b7280); min-width: 28px }
</style>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/__tests__/RandomPage.test.ts`
Expected: PASS（4 个源切换 case）。

- [ ] **Step 5: Commit**

```bash
cd frontend && npx vitest run src/__tests__/RandomPage.test.ts
git add frontend/src/views/RandomPage.vue frontend/src/__tests__/RandomPage.test.ts
git commit -m "feat(cf): RandomPage source switch (gallery/characters/artists) (P3 Task 3)"
```

---

### Task 4: CfFavoritesPage 收藏夹页

**Files:**
- Create: `frontend/src/views/CfFavoritesPage.vue`
- Test: `frontend/src/__tests__/CfFavoritesPage.test.ts`

**Interfaces:**
- Consumes:
  - `listCfFavorites(kind)` from Task 1 → `{ items: CfListItem[] }`
  - `toggleCharacterFavorite(source, key)` / `toggleArtistFavorite(source, key)` from P2 → `{ favorite }`
  - `parseEntryKey(ek) → { kind, source, key }` from P2
  - `ImageCard` props（同 Task 3）
  - 视觉仿 `CollectionListPage`：filter-bar（n-card）+ 前端子串搜索 + n-grid cols `2 600:3 900:5 1200:6` + n-empty
- Produces: `CfFavoritesPage` 默认导出（Task 6 router 注册 `/cf/favorites`）

**设计要点**：
- `kind: 'char' | 'artist'`（默认 `'char'`，tab 切换）；`items`；`keyword`（前端子串过滤 name/tag）。
- `load()` 调 `listCfFavorites(kind)`；切 tab 重载。
- **乐观移除**：toggle 收藏（点掉）后从 `items` filter 移除（不再属于收藏列表）。toggle 收藏（点亮）理论上收藏页不触发，但点掉是主路径。
- 前端子串搜索：keyword 命中 `name` 或 `core_tags`/`tag` 即保留（cf 收藏量级小，无需后端分页）。

- [ ] **Step 1: Write the failing test**

`frontend/src/__tests__/CfFavoritesPage.test.ts`（新建）：

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import CfFavoritesPage from '../views/CfFavoritesPage.vue'

const favData: Record<string, any> = {
  char: { items: [
    { entry_key: 'char:danbooru:1', source: 'danbooru', name: 'Hatsune Miku', core_tags: 'vocaloid,twins', favorite: true },
    { entry_key: 'char:danbooru:2', source: 'danbooru', name: 'Kafka', core_tags: 'hsr', favorite: true },
  ] },
  artist: { items: [
    { entry_key: 'artist:anima:a1', source: 'anima', name: 'Artist One', tag: 'cool', favorite: true },
  ] },
}

vi.mock('../api/characterfinder', () => ({
  listCfFavorites: vi.fn(async (kind: string) => favData[kind] || { items: [] }),
  toggleCharacterFavorite: vi.fn(async () => ({ favorite: false })),
  toggleArtistFavorite: vi.fn(async () => ({ favorite: false })),
  parseEntryKey: (ek: string) => {
    const p = ek.split(':'); return { kind: p[0], source: p[1], key: p.slice(2).join(':') }
  },
}))

import { listCfFavorites, toggleCharacterFavorite } from '../api/characterfinder'

describe('CfFavoritesPage', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('默认 kind=char 加载角色收藏', async () => {
    mount(CfFavoritesPage); await flushPromises()
    expect(listCfFavorites).toHaveBeenCalledWith('char')
  })

  it('切 tab 到 artist 加载艺术家收藏', async () => {
    const w = mount(CfFavoritesPage); await flushPromises()
    ;(listCfFavorites as any).mockClear()
    // NTabs v-model:value 经 @update:value 触发（比点 NTab 更可靠）
    await w.findComponent({ name: 'NTabs' }).vm.$emit('update:value', 'artist')
    await flushPromises()
    expect(listCfFavorites).toHaveBeenCalledWith('artist')
  })

  it('渲染收藏项卡片（角色 2 项）', async () => {
    const w = mount(CfFavoritesPage); await flushPromises()
    const cards = w.findAllComponents({ name: 'ImageCard' })
    expect(cards.length).toBe(2)
  })

  it('toggle 收藏后乐观移除该卡', async () => {
    const w = mount(CfFavoritesPage); await flushPromises()
    expect(w.findAllComponents({ name: 'ImageCard' }).length).toBe(2)
    const card = w.findAllComponents({ name: 'ImageCard' })[0]
    await card.vm.$emit('toggle-favorite')
    await flushPromises()  // onToggleFav 是 async，需 flush 等 filter 生效
    expect(toggleCharacterFavorite).toHaveBeenCalled()
    expect(w.findAllComponents({ name: 'ImageCard' }).length).toBe(1)
  })

  it('前端搜索过滤 name', async () => {
    const w = mount(CfFavoritesPage); await flushPromises()
    const input = w.findComponent({ name: 'NInput' })
    await input.vm.$emit('update:value', 'kafka')
    await flushPromises()
    const cards = w.findAllComponents({ name: 'ImageCard' })
    expect(cards.length).toBe(1)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/__tests__/CfFavoritesPage.test.ts`
Expected: FAIL — `Cannot find module '../views/CfFavoritesPage.vue'`（组件未创建）。

- [ ] **Step 3: Write minimal implementation**

`frontend/src/views/CfFavoritesPage.vue`（新建）：

```vue
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { NCard, NTabs, NTab, NInput, NGrid, NGridItem, NEmpty, useMessage } from 'naive-ui'
import {
  listCfFavorites, toggleCharacterFavorite, toggleArtistFavorite, parseEntryKey,
  type CfListItem,
} from '../api/characterfinder'
import ImageCard from '../components/ImageCard.vue'

const msg = useMessage()
const kind = ref<'char' | 'artist'>('char')
const items = ref<CfListItem[]>([])
const keyword = ref('')
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    items.value = (await listCfFavorites(kind.value)).items
  } catch (e: any) { msg.error('加载失败：' + e.message) } finally { loading.value = false }
}
onMounted(load)

function onKind(v: 'char' | 'artist') { kind.value = v; load() }

// 前端子串过滤（收藏量级小，无需后端分页）
const filtered = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  if (!k) return items.value
  return items.value.filter(it =>
    (it.name || '').toLowerCase().includes(k) ||
    (it.core_tags || it.tag || '').toLowerCase().includes(k),
  )
})

function cardTo(it: CfListItem): string {
  const { source: s, key } = parseEntryKey(it.entry_key)
  return kind.value === 'artist' ? `/artists/${s}/${encodeURIComponent(key)}` : `/characters/${s}/${encodeURIComponent(key)}`
}
function cardImg(it: CfListItem): string {
  return kind.value === 'artist' ? (it.thumb1_url || '') : (it.thumb_url || '')
}
function cardTags(it: CfListItem): string[] {
  const raw = kind.value === 'artist' ? (it.tag || '') : (it.core_tags || '')
  return raw.split(',').map(t => t.trim()).filter(Boolean)
}

// 乐观移除：点掉收藏后从列表移除（不再属于收藏列表）
async function onToggleFav(it: CfListItem) {
  const { source: s, key } = parseEntryKey(it.entry_key)
  try {
    const r = kind.value === 'artist'
      ? await toggleArtistFavorite(s, key)
      : await toggleCharacterFavorite(s, key)
    if (!r.favorite) items.value = items.value.filter(i => i.entry_key !== it.entry_key)
  } catch (e: any) { msg.error('操作失败：' + e.message) }
}
</script>

<template>
  <n-card size="small" class="filter-bar" style="margin-bottom:16px">
    <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">
      <n-tabs type="line" :value="kind" size="small" @update:value="onKind">
        <n-tab name="char">角色收藏</n-tab>
        <n-tab name="artist">艺术家收藏</n-tab>
      </n-tabs>
      <n-input :value="keyword" placeholder="搜索名称 / tag" size="small" clearable
               @update:value="(v: string) => keyword = v"
               style="min-width:220px;max-width:300px" />
    </div>
  </n-card>
  <n-empty v-if="!filtered.length" :description="keyword ? '没有符合条件的收藏' : '还没有收藏，去角色/艺术家列表收藏吧'" />
  <n-grid v-else cols="2 600:3 900:5 1200:6" :x-gap="12" :y-gap="12">
    <n-grid-item v-for="it in filtered" :key="it.entry_key">
      <ImageCard :item="it" :to="cardTo(it)" :img-src="cardImg(it)"
                 :title-text="it.name || ''" :tags-list="cardTags(it)"
                 :favorite="it.favorite" @toggle-favorite="onToggleFav(it)" />
    </n-grid-item>
  </n-grid>
</template>

<style scoped>
.field { display: flex; align-items: center; gap: 8px }
.field-label { font-size: 13px; font-weight: 600; color: var(--n-text-color-3, #6b7280); min-width: 28px }
</style>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/__tests__/CfFavoritesPage.test.ts`
Expected: PASS（5 个 case：默认 char / 切 artist / 渲染 / 乐观移除 / 搜索）。

- [ ] **Step 5: Commit**

```bash
cd frontend && npx vitest run src/__tests__/CfFavoritesPage.test.ts
git add frontend/src/views/CfFavoritesPage.vue frontend/src/__tests__/CfFavoritesPage.test.ts
git commit -m "feat(cf): CfFavoritesPage with tabs + optimistic removal + search (P3 Task 4)"
```

---

### Task 5: 列表页最近查看区（CharactersPage + ArtistsPage）

**Files:**
- Modify: `frontend/src/views/CharactersPage.vue`（`onMounted` 加 `listCfRecent`；模板 filter-bar 之前加横向滚动区）
- Modify: `frontend/src/views/ArtistsPage.vue`（同）
- Test: `frontend/src/__tests__/CharactersPage.test.ts`、`frontend/src/__tests__/ArtistsPage.test.ts`

**Interfaces:**
- Consumes:
  - `listCfRecent(kind, limit=10)` from Task 1 → `{ items: CfListItem[] }`
  - CharactersPage 用 `'char'`；ArtistsPage 用 `'artist'`
  - 现有 `ImageCard` + 现有 `cardTo` / `cardImg`（两个页面已有，最近查看区复用）

**设计要点**：
- `recentItems` ref，`onMounted` 调 `listCfRecent(kind, 10)`。
- 模板 filter-bar **之前**加横向滚动区，`v-if="recentItems.length"`（空时整区隐藏，不显示空态）。
- 小卡片固定窄宽（每张 ~140px），点击跳详情（复用 cardTo / cardImg）。

- [ ] **Step 1: Write the failing test**

**CharactersPage.test.ts** — 在文件顶部 mock 块追加 `listCfRecent`（仿现有 `searchCharacters` / `listCharacterSeries` mock 模式；若文件已 mock `../api/characterfinder`，在返回对象里补 `listCfRecent`）。追加测试：

```ts
describe('CharactersPage 最近查看区', () => {
  it('recent 非空时渲染横向卡片，空时隐藏', async () => {
    // 假设现有 mock 已含 searchCharacters 等；此处依赖 listCfRecent 返回 2 项
    const w = mount(CharactersPage); await nextTick(); await nextTick()
    const recent = w.find('.recent-bar')
    expect(recent.exists()).toBe(true)
    expect(w.findAllComponents({ name: 'ImageCard' }).length).toBeGreaterThan(0)
  })
})
```

> **实现者注意**：`CharactersPage.test.ts` 现有 mock 结构以文件实际内容为准。把 `listCfRecent` 加进 `vi.mock('../api/characterfinder', ...)` 的返回对象，返回 `{ items: [{ entry_key: 'char:danbooru:r1', source: 'danbooru', name: 'Recent One', core_tags: 'x', favorite: false, thumb_url: '' }] }`。断言 `.recent-bar` 存在且渲染了 ImageCard；再补一个 `listCfRecent` 返回 `{items:[]}` 时 `.recent-bar` 不存在的 case。对齐现有 mock/挂载模式（`mount(CharactersPage)` + `await nextTick()`）。

**ArtistsPage.test.ts** — 同理追加（`listCfRecent('artist', 10)`，断言 `.recent-bar`）。

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/__tests__/CharactersPage.test.ts src/__tests__/ArtistsPage.test.ts`
Expected: FAIL — `.recent-bar` 不存在（模板未加）。

- [ ] **Step 3: Write minimal implementation**

**CharactersPage.vue** — `<script setup>` 改动：

import 行追加 `listCfRecent`：
```ts
import {
  searchCharacters, listCharacterSeries, toggleCharacterFavorite, listCfRecent, parseEntryKey,
  type CfListItem,
} from '../api/characterfinder'
```

在 `const seriesOptions = ref<...>([])` 之后、`let lastReq = 0` 之前加：
```ts
const recentItems = ref<CfListItem[]>([])
```

`onMounted` 改为加载最近查看（静默，失败不影响主列表）：
```ts
onMounted(() => {
  load(); loadSeries()
  listCfRecent('char', 10).then(r => { recentItems.value = r.items }).catch(() => {})
})
```

`<template>` 在 `<n-card class="filter-bar" ...>` **之前**插入：
```html
  <div v-if="recentItems.length" class="recent-bar">
    <span class="recent-label">最近查看</span>
    <div class="recent-scroll">
      <ImageCard v-for="it in recentItems" :key="it.entry_key" :item="it" :to="cardTo(it)"
                 :img-src="cardImg(it)" :title-text="it.name || ''"
                 :tags-list="cardTags(it)" :favorite="it.favorite" style="width:140px" />
    </div>
  </div>
```

`<style scoped>` 末尾追加：
```css
.recent-bar { margin-bottom: 12px }
.recent-label { font-size: 12px; font-weight: 600; color: var(--n-text-color-3, #6b7280) }
.recent-scroll {
  display: flex; gap: 8px; overflow-x: auto; padding: 6px 0 4px;
}
.recent-scroll :deep(.card) { flex: 0 0 140px }
```

**ArtistsPage.vue** — 同构改动（kind 用 `'artist'`）：

import 行追加 `listCfRecent`：
```ts
import { searchArtists, toggleArtistFavorite, listCfRecent, parseEntryKey } from '../api/characterfinder'
```

在 `const items = ref<any[]>([])` 之后加：
```ts
const recentItems = ref<any[]>([])
```

`onMounted` 改为：
```ts
onMounted(() => {
  load()
  listCfRecent('artist', 10).then(r => { recentItems.value = r.items }).catch(() => {})
})
```

`<template>` 在 `<n-card class="filter-bar">` **之前**插入（复用 ArtistsPage 现有 `cardTo` / `cardImg` / `cardTags`）：
```html
  <div v-if="recentItems.length" class="recent-bar">
    <span class="recent-label">最近查看</span>
    <div class="recent-scroll">
      <ImageCard v-for="it in recentItems" :key="it.entry_key" :item="it" :to="cardTo(it)"
                 :img-src="cardImg(it)" :title-text="it.name || ''"
                 :tags-list="cardTags(it)" :favorite="!!it.favorite" style="width:140px" />
    </div>
  </div>
```

`<style scoped>` 末尾追加：
```css
.recent-bar { margin-bottom: 12px }
.recent-label { font-size: 12px; font-weight: 600; color: var(--n-text-color-3, #6b7280) }
.recent-scroll { display: flex; gap: 8px; overflow-x: auto; padding: 6px 0 4px }
.recent-scroll :deep(.card) { flex: 0 0 140px }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/__tests__/CharactersPage.test.ts src/__tests__/ArtistsPage.test.ts`
Expected: PASS（含新增最近查看 case + 原有列表/收藏/toggle case 不退化）。

- [ ] **Step 5: Commit**

```bash
cd frontend && npx vitest run src/__tests__/CharactersPage.test.ts src/__tests__/ArtistsPage.test.ts
git add frontend/src/views/CharactersPage.vue frontend/src/views/ArtistsPage.vue \
        frontend/src/__tests__/CharactersPage.test.ts frontend/src/__tests__/ArtistsPage.test.ts
git commit -m "feat(cf): recent-view strip on Characters/ArtistsPage (P3 Task 5)"
```

---

### Task 6: router + App + icon 接线

**Files:**
- Modify: `frontend/src/router.ts`（import + route）
- Modify: `frontend/src/App.vue`（icon import + ITEMS）
- Test: `frontend/src/__tests__/router.test.ts`

**Interfaces:**
- Consumes: `CfFavoritesPage`（Task 4 产出）、`IconBookmark`（Task 2 产出）
- Produces: `/cf/favorites` 路由 + 「cf 收藏」菜单项

**设计要点**：
- router import **带 `.vue` 后缀**（漏 → vue-tsc TS2307）。
- App.vue icon import 块加 `IconBookmark`；ITEMS 加 `{ label: 'cf 收藏', key: '/cf/favorites', icon: IconBookmark }`（插在「艺术家」之后）。activeKey longest-prefix 自动解析，无需改 activeKey 逻辑。

- [ ] **Step 1: Write the failing test**

`frontend/src/__tests__/router.test.ts` — 在现有路由断言旁（对齐文件已有的 `expect(router.getRoutes()...)` 或 `routes.find(...)` 风格）追加：

```ts
it('/cf/favorites 路由已注册', () => {
  const hit = router.getRoutes().find(r => r.path === '/cf/favorites')
  expect(hit).toBeTruthy()
})
```

> **实现者注意**：以 `router.test.ts` 现有断言风格为准（P2 已用 `import { router } from '../router'` named import）。若文件用 `router.resolve('/cf/favorites')` 风格，改为等价断言。

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/__tests__/router.test.ts`
Expected: FAIL — `/cf/favorites` 路由未注册（find 返回 undefined）。

- [ ] **Step 3: Write minimal implementation**

**router.ts** — import 块（在 `import ArtistDetailPage from './views/ArtistDetailPage.vue'` 之后）加：
```ts
import CfFavoritesPage from './views/CfFavoritesPage.vue'
```

routes 数组（在 `{ path: '/artists/:source/:key', ... }` 之后）加：
```ts
    { path: '/cf/favorites', component: CfFavoritesPage },
```

**App.vue** — icon import 块加 `IconBookmark`：
```ts
import {
  IconUpload, IconGallery, IconRandom, IconStar, IconEdit, IconSettings,
  IconSun, IconMoon, IconMonitor, IconFolderTag, IconCharacter, IconArtist, IconBookmark,
} from './components/icons'
```

ITEMS 数组（在「艺术家」之后插入「cf 收藏」）：
```ts
const ITEMS = [
  { label: '上传', key: '/upload', icon: IconUpload },
  { label: '路径打标', key: '/pathtag', icon: IconFolderTag },
  { label: '图库', key: '/gallery', icon: IconGallery },
  { label: '角色图鉴', key: '/characters', icon: IconCharacter },
  { label: '艺术家', key: '/artists', icon: IconArtist },
  { label: 'cf 收藏', key: '/cf/favorites', icon: IconBookmark },
  { label: '随机', key: '/random', icon: IconRandom },
  { label: '收藏列表', key: '/collections', icon: IconStar },
  { label: '提示词收藏', key: '/promptbox', icon: IconEdit },
  { label: '设置', key: '/settings', icon: IconSettings },
] as const
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/__tests__/router.test.ts`
Expected: PASS（`/cf/favorites` 注册）。

- [ ] **Step 5: Commit**

```bash
cd frontend && npx vitest run src/__tests__/router.test.ts
git add frontend/src/router.ts frontend/src/App.vue frontend/src/__tests__/router.test.ts
git commit -m "feat(cf): wire /cf/favorites route + menu (P3 Task 6)"
```

---

## 最终全量回归

所有任务完成后：

```bash
cd frontend && npx vitest run          # 期望：全绿（P2 基线 160 + P3 新增 ≈ 20+）
cd frontend && npm run build           # 期望：vue-tsc 0 exit（无类型错误）
```

任一失败则回到对应任务修复。

---

## Self-Review

**1. Spec 覆盖**（对照 `docs/superpowers/specs/2026-06-21-characterfinder-frontend-p3-design.md` 6 节）：

| Spec 节 | 覆盖任务 |
|---|---|
| §1 cf API 扩展（listCfFavorites/listCfRecent/randomCf） | Task 1 ✓ |
| §2 RandomPage 源切换（gallery/characters/artists + cfSource） | Task 3 ✓ |
| §3 CfFavoritesPage（tab + 乐观移除 + 前端搜索） | Task 4 ✓ |
| §4 列表页最近查看区（CharactersPage + ArtistsPage） | Task 5 ✓ |
| §5 router + App + icon（IconBookmark + /cf/favorites + 菜单） | Task 2（icon）+ Task 6（router/App）✓ |
| §测试策略（API URL 断言 / 源切换 / tab / 乐观移除 / recent / router） | 各任务 Step 1 ✓ |

无遗漏节。

**2. Placeholder 扫描**：
- Task 5 / Task 6 测试步骤含「实现者注意」对齐现有 mock/断言风格 — 这是因为 `CharactersPage.test.ts` / `ArtistsPage.test.ts` / `router.test.ts` 的精确内部结构未在 plan 中全文展开，但给出了具体可粘贴的测试代码 + 对齐指引（mock 返回值、断言目标 `.recent-bar` / `/cf/favorites`）。其余任务（1/2/3/4）每步代码完整可粘贴。
- 无 TBD / TODO / "implement later" / "similar to Task N"。

**3. 类型一致**：
- `listCfFavorites(kind: 'char'|'artist')` — Task 1 定义、Task 4 (`listCfFavorites(kind.value)`, kind.value 为 'char'|'artist') 消费 ✓
- `listCfRecent(kind, limit=10)` — Task 1 定义、Task 5 (`listCfRecent('char', 10)` / `listCfRecent('artist', 10)`) 消费 ✓
- `randomCf(type, source, size=24)` — Task 1 定义、Task 3 (`randomCf(type, cfSource.value, size)`) 消费 ✓
- `IconBookmark` — Task 2 定义、Task 6 App.vue 消费 ✓
- `CfFavoritesPage` 默认导出 — Task 4 定义、Task 6 router import 消费 ✓
- ImageCard props（`to` / `imgSrc` / `titleText` / `tagsList` / `favorite` / `@toggle-favorite`）跨 Task 3/4/5 一致 ✓
- `parseEntryKey` 对象解构 `const { source: s, key } = parseEntryKey(...)` 跨 Task 3/4 一致 ✓

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-21-characterfinder-frontend-p3.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — 每个 task 派 fresh 实现者 + task 评审（spec + quality），最后整分支评审。延续 P2 已验证模式。

**2. Inline Execution** — 本会话内 executing-plans 批量执行 + 检查点。

**Which approach?**
