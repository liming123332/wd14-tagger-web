# Characterfinder 前端 P2 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 wd14-tagger-web 前端新增"角色图鉴 / 艺术家"浏览与编辑能力——列表页（搜索/源切换/系列筛选/收藏过滤）+ 详情页（复用现有 DetailPage 双栏布局 + 🔒 锁定标签 + 反推/重分类/编辑/换图/收藏），与现有图库/收藏页风格完全一致。

**Architecture:** 复用 P1 已合并到 master 的后端 `/api/cf/*` 契约（权威只读 + overlay 可编辑）。前端新增扁平 `fetch` 客户端 `characterfinder.ts`（仿 `client.ts`），通用化 `ImageCard`/`TagEditor`（向后兼容可选 props），新增 4 个页面组件（列表×2 + 详情×2），在 `router.ts`/`App.vue` 注册。详情页复刻 `PromptboxDetailPage` 的双栏 + `TagEditor × 6` + 模式切换范式；差异：右栏顶部新增只读 🔒 锁定标签区（trigger+core_tags / 画师 tag），图片走 `/api/cf/asset`（本地优先 + CDN 回退），save body 不含 `locked_tags`。

**Tech Stack:** Vue 3.5 (`<script setup lang="ts">`) · naive-ui 2.44 · vue-router 4.6 · vitest 4 + @vue/test-utils 2 + jsdom（前端已有测试基建，**无新增 npm 依赖**）。

## Global Constraints

- **前端无新增 npm 依赖**（设计 §8）。复用现有 vitest / @vue/test-utils / jsdom。
- **API 客户端风格**：`const base = ''` + 原生 `fetch` + 扁平导出函数，仿 [frontend/src/api/client.ts](frontend/src/api/client.ts)。anima 的 `key` 含空格/逗号/括号 → 所有带 key 的 URL 必须 `encodeURIComponent(key)`；`source`（danbooru/e621/anima）无特殊字符可不编码，但统一编码更安全。
- **entry_key 复合键**：`{kind}:{source}:{key}`，kind∈`char|artist`，source∈`danbooru|e621|anima`。前端用 `parseEntryKey(ek)` 拆分（key 可能含冒号，只切前两段：`parts.slice(2).join(':')`）。
- **列表页风格 = [GalleryPage.vue](frontend/src/views/GalleryPage.vue)**：`n-card size="small"` 筛选栏 + `n-grid cols="2 600:3 900:5 1200:6" :x-gap="12" :y-gap="12"` + `NPagination`，复用通用化 `ImageCard`。
- **详情页风格 = [PromptboxDetailPage.vue](frontend/src/views/PromptboxDetailPage.vue) / [DetailPage.vue](frontend/src/views/DetailPage.vue)**：`grid-template-columns:minmax(280px,1fr) minmax(0,2fr)` 双栏；左栏图片+模型选择+阈值+自定义标签+操作按钮；右栏 `NRadioGroup`(tags/phrase) + `TagEditor × KEY_TITLES` + extras `TagEditor`。`KEY_TITLES` 6 类与颜色逐字复用（见 Task 7）。
- **🔒 锁定标签不可绕过**（最高优先级，对应设计 §5.4 / §10）：`locked_tags` 来自后端权威（角色 trigger+core_tags、艺术家画师 tag），前端**只读展示**；`buildPromptWithLocked` 始终把锁定标签**前置**；save 的 PUT body 只含 `{categories, extras, custom_tags}`，**绝不**含 `locked_tags` 字段。
- **组件通用化必须向后兼容**：`ImageCard`/`TagEditor` 新增 prop 全部可选，不传时行为与现状完全一致；现有 `ImageCard.test.ts`/`TagEditor.test.ts`/`GalleryPage.test.ts` 必须继续全绿。
- **后端契约由 P1 pytest 覆盖**（已合并 master，231 passed），前端不重复测后端逻辑，只测前端封装（URL 构造、请求体形状、组件渲染/交互）。
- **TDD**：每个 task 先写失败 vitest → `npx vitest run` 红 → 实现 → 绿 → `npm run build`(vue-tsc) 类型检查 → commit。
- **图片显示**：缩略图/详情图统一经 `cfAssetUrl(kind, source, key, which)` → `/api/cf/asset`（后端三层回退：overlay 替换图 → 本地下载/拷贝图 → 307 CDN）。

## File Structure

| 文件 | 职责 | 动作 |
|---|---|---|
| `frontend/src/api/characterfinder.ts` | cf 所有 fetch 封装 + 类型 + `parseEntryKey` + `cfAssetUrl` | 新建（Task 1） |
| `frontend/src/detail-utils.ts` | 加 `buildPromptWithLocked(meta, lockedTags)`（锁定标签前置） | 改（Task 2） |
| `frontend/src/components/ImageCard.vue` | 通用化：加可选 `to/imgSrc/titleText/tagsList/copyText/downloadSrc/downloadName/favorite` + emit `toggle-favorite` | 改（Task 3） |
| `frontend/src/components/TagEditor.vue` | 加可选 `lockedTags?: string[]`，渲染只读 🔒 chip | 改（Task 4） |
| `frontend/src/components/icons.ts` | 加 `IconCharacter`/`IconArtist` | 改（Task 5） |
| `frontend/src/router.ts` | 加 `/characters`、`/characters/:source/:key`、`/artists`、`/artists/:source/:key` | 改（Task 5） |
| `frontend/src/App.vue` | `ITEMS` 加"角色图鉴"/"艺术家"两项 + `currentTitle` 详情特判 | 改（Task 5） |
| `frontend/src/views/CharactersPage.vue` | 角色列表页（仿 GalleryPage + source tab + 系列下拉） | 新建（Task 6） |
| `frontend/src/views/CharacterDetailPage.vue` | 角色详情页（仿 PromptboxDetailPage + 锁定标签区 + 换图/收藏） | 新建（Task 7） |
| `frontend/src/views/ArtistsPage.vue` | 艺术家列表页（双图缩略取 thumb1） | 新建（Task 8） |
| `frontend/src/views/ArtistDetailPage.vue` | 艺术家详情页（双图 thumb1/thumb2） | 新建（Task 8） |
| `frontend/src/__tests__/characterfinder.test.ts` | cf 客户端测试 | 新建（Task 1） |
| `frontend/src/__tests__/{detail,ImageCard,TagEditor,App,icons}.test.ts` | 对应增强的测试扩展 | 改（Task 2-5） |
| `frontend/src/__tests__/{CharactersPage,CharacterDetailPage,ArtistsPage,ArtistDetailPage}.test.ts` | 页面测试 | 新建（Task 6-8） |

**后端契约速查（P1 已实现，前端只消费）：**
- `GET /api/cf/characters?query=&source=&series=&page=&size=` → `{items:[{entry_key,source,name,series,trigger,core_tags,thumb_url,image_url,favorite}], total}`
- `GET /api/cf/characters/series?source=` → `[{series,count}]`
- `GET /api/cf/character?source=&key=` → 权威+overlay 合并：`{entry_key,source,name,series,trigger,core_tags,thumb_url,image_url,favorite,locked_tags,categories:{k:{tags,phrase,user_edited}},extras:{tags,phrase,user_edited},custom_tags,model,gen_threshold,char_threshold,image_override}`
- `POST /api/cf/character/tag?source=&key=` body `{model,gen_th,char_th,use_char}` → 合并详情
- `POST /api/cf/character/reclassify?source=&key=` body `{keep:{k:[...]}}` → 合并详情
- `PUT /api/cf/character?source=&key=` body `{categories,extras,custom_tags}`（无 locked_tags）→ 合并详情
- `POST /api/cf/character/image?source=&key=` multipart `file` → `{image_override}`
- `POST /api/cf/character/favorite?source=&key=` → `{favorite}`
- 艺术家同构：`/api/cf/artists`(search, item 多 `tag/thumb1_url/thumb2_url`、无 trigger/core_tags)、`/api/cf/artist`(detail)、`/api/cf/artist/{tag,reclassify,image,favorite}`（注意单数 `artist`、复数 `artists`）
- `GET /api/cf/asset?kind=&source=&key=&which=` → 图片（which：角色 `thumb|image`，艺术家 `1|2`）

---

### Task 1: cf API 客户端 `characterfinder.ts`

**Files:**
- Create: `frontend/src/api/characterfinder.ts`
- Test: `frontend/src/__tests__/characterfinder.test.ts`

**Interfaces:**
- Consumes: 后端 `/api/cf/*`（P1）
- Produces: `parseEntryKey`、`cfAssetUrl`、`searchCharacters`/`getCharacter`/`tagCharacter`/`reclassifyCharacter`/`saveCharacter`/`uploadCharacterImage`/`toggleCharacterFavorite`/`listCharacterSeries` + 艺术家同构 8 个函数 + 类型 `CfListItem`/`CfCategoryView`/`CfDetail`

- [ ] **Step 1: 写失败测试**

Create `frontend/src/__tests__/characterfinder.test.ts`:
```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  parseEntryKey, cfAssetUrl,
  searchCharacters, listCharacterSeries, getCharacter,
  tagCharacter, reclassifyCharacter, saveCharacter,
  uploadCharacterImage, toggleCharacterFavorite,
  searchArtists, getArtist, tagArtist, reclassifyArtist, saveArtist,
  uploadArtistImage, toggleArtistFavorite,
} from '../api/characterfinder'

describe('parseEntryKey', () => {
  it('拆 {kind}:{source}:{key}', () => {
    expect(parseEntryKey('char:danbooru:123')).toEqual({ kind: 'char', source: 'danbooru', key: '123' })
    expect(parseEntryKey('artist:anima:2b (nier_automata)')).toEqual({ kind: 'artist', source: 'anima', key: '2b (nier_automata)' })
  })
  it('key 含冒号时只切前两段', () => {
    expect(parseEntryKey('char:danbooru:a:b:c')).toEqual({ kind: 'char', source: 'danbooru', key: 'a:b:c' })
  })
})

describe('cfAssetUrl', () => {
  it('拼 /api/cf/asset 带 4 个 query', () => {
    expect(cfAssetUrl('char', 'danbooru', '123', 'thumb')).toBe('/api/cf/asset?kind=char&source=danbooru&key=123&which=thumb')
  })
  it('key 含特殊字符时编码', () => {
    expect(cfAssetUrl('char', 'anima', '2b (nier)', 'image')).toBe('/api/cf/asset?kind=char&source=anima&key=2b%20(nier)&which=image')
  })
})

describe('searchCharacters', () => {
  beforeEach(() => vi.unstubAllGlobals())
  it('GET /api/cf/characters 带 source/page/size，series 可选', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url); return { ok: true, json: async () => ({ items: [], total: 0 }) } as any
    }))
    await searchCharacters('miku', 'danbooru', 'vocaloid', 2, 50)
    expect(urls[0]).toContain('/api/cf/characters?')
    expect(urls[0]).toContain('query=miku')
    expect(urls[0]).toContain('source=danbooru')
    expect(urls[0]).toContain('series=vocaloid')
    expect(urls[0]).toContain('page=2')
    expect(urls[0]).toContain('size=50')
  })
  it('无 series 时不带 series 参数', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url); return { ok: true, json: async () => ({ items: [], total: 0 }) } as any
    }))
    await searchCharacters('', 'anima')
    expect(urls[0]).not.toContain('series=')
  })
})

describe('listCharacterSeries', () => {
  beforeEach(() => vi.unstubAllGlobals())
  it('GET /api/cf/characters/series?source=', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url); return { ok: true, json: async () => [{ series: 'vocaloid', count: 3 }] } as any
    }))
    const r = await listCharacterSeries('danbooru')
    expect(urls[0]).toBe('/api/cf/characters/series?source=danbooru')
    expect(r[0]).toEqual({ series: 'vocaloid', count: 3 })
  })
})

describe('getCharacter', () => {
  beforeEach(() => vi.unstubAllGlobals())
  it('GET /api/cf/character?source=&key=，key 编码', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url); return { ok: true, json: async () => ({ entry_key: 'x' }) } as any
    }))
    await getCharacter('anima', '2b (nier)')
    expect(urls[0]).toBe('/api/cf/character?source=anima&key=2b%20(nier)')
  })
})

describe('tagCharacter', () => {
  beforeEach(() => vi.unstubAllGlobals())
  it('POST /api/cf/character/tag?source=&key= 带 model/gen_th/char_th/use_char', async () => {
    const seen: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts: any) => {
      seen.push({ url, body: opts.body }); return { ok: true, json: async () => ({}) } as any
    }))
    await tagCharacter('danbooru', '1', 0.35, 0.9, 'wd14')
    expect(seen[0].url).toBe('/api/cf/character/tag?source=danbooru&key=1')
    expect(JSON.parse(seen[0].body)).toMatchObject({ model: 'wd14', gen_th: 0.35, char_th: 0.9, use_char: true })
  })
})

describe('reclassifyCharacter', () => {
  beforeEach(() => vi.unstubAllGlobals())
  it('POST /api/cf/character/reclassify 带 keep', async () => {
    const seen: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts: any) => {
      seen.push({ url, body: opts.body }); return { ok: true, json: async () => ({}) } as any
    }))
    await reclassifyCharacter('danbooru', '1', { head: ['my tag'] })
    expect(seen[0].url).toBe('/api/cf/character/reclassify?source=danbooru&key=1')
    expect(JSON.parse(seen[0].body)).toEqual({ keep: { head: ['my tag'] } })
  })
})

describe('saveCharacter', () => {
  beforeEach(() => vi.unstubAllGlobals())
  it('PUT /api/cf/character body 含 categories/extras/custom_tags，不含 locked_tags', async () => {
    const seen: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts: any) => {
      seen.push({ url, method: opts.method, body: opts.body }); return { ok: true, json: async () => ({}) } as any
    }))
    await saveCharacter('danbooru', '1', {
      categories: { head: { tags: ['x'], phrase: 'x', user_edited: true } },
      extras: { tags: [], phrase: '', user_edited: false },
      custom_tags: ['fav'],
    })
    expect(seen[0].url).toBe('/api/cf/character?source=danbooru&key=1')
    expect(seen[0].method).toBe('PUT')
    const body = JSON.parse(seen[0].body)
    expect(body.categories.head.tags).toEqual(['x'])
    expect(body.custom_tags).toEqual(['fav'])
    expect(body.locked_tags).toBeUndefined()  // 锁定标签绝不发回后端
  })
})

describe('uploadCharacterImage', () => {
  beforeEach(() => vi.unstubAllGlobals())
  it('POST FormData 到 /api/cf/character/image', async () => {
    const seen: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts: any) => {
      seen.push({ url, body: opts.body }); return { ok: true, json: async () => ({ image_override: 'a.png' }) } as any
    }))
    const r = await uploadCharacterImage('danbooru', '1', new File(['x'], 'a.png'))
    expect(seen[0].url).toBe('/api/cf/character/image?source=danbooru&key=1')
    expect(seen[0].body).toBeInstanceOf(FormData)
    expect(seen[0].body.get('file')).toBeTruthy()
    expect(r).toEqual({ image_override: 'a.png' })
  })
})

describe('toggleCharacterFavorite', () => {
  beforeEach(() => vi.unstubAllGlobals())
  it('POST /api/cf/character/favorite 返回 {favorite}', async () => {
    const seen: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts: any) => {
      seen.push({ url, method: opts.method }); return { ok: true, json: async () => ({ favorite: true }) } as any
    }))
    const r = await toggleCharacterFavorite('danbooru', '1')
    expect(seen[0].url).toBe('/api/cf/character/favorite?source=danbooru&key=1')
    expect(seen[0].method).toBe('POST')
    expect(r).toEqual({ favorite: true })
  })
})

describe('artists 同构', () => {
  beforeEach(() => vi.unstubAllGlobals())
  it('searchArtists → /api/cf/artists', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url); return { ok: true, json: async () => ({ items: [], total: 0 }) } as any
    }))
    await searchArtists('ebi', 'danbooru', 1, 50)
    expect(urls[0]).toContain('/api/cf/artists?')
    expect(urls[0]).toContain('query=ebi')
  })
  it('getArtist → /api/cf/artist（单数）', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url); return { ok: true, json: async () => ({}) } as any
    }))
    await getArtist('danbooru', '1')
    expect(urls[0]).toBe('/api/cf/artist?source=danbooru&key=1')
  })
  it('tagArtist → /api/cf/artist/tag', async () => {
    const seen: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts: any) => {
      seen.push({ url, body: opts.body }); return { ok: true, json: async () => ({}) } as any
    }))
    await tagArtist('danbooru', '1', 0.35, 0.9, 'wd14')
    expect(seen[0].url).toBe('/api/cf/artist/tag?source=danbooru&key=1')
  })
  it('saveArtist PUT 不含 locked_tags', async () => {
    const seen: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts: any) => {
      seen.push({ body: opts.body }); return { ok: true, json: async () => ({}) } as any
    }))
    await saveArtist('danbooru', '1', { categories: {}, extras: { tags: [], phrase: '', user_edited: false }, custom_tags: [] })
    expect(JSON.parse(seen[0].body).locked_tags).toBeUndefined()
  })
  it('uploadArtistImage / toggleArtistFavorite 路径', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url); return { ok: true, json: async () => ({}) } as any
    }))
    await uploadArtistImage('danbooru', '1', new File(['x'], 'a.png'))
    await toggleArtistFavorite('danbooru', '1')
    expect(urls[0]).toBe('/api/cf/artist/image?source=danbooru&key=1')
    expect(urls[1]).toBe('/api/cf/artist/favorite?source=danbooru&key=1')
  })
  it('reclassifyArtist 带 keep', async () => {
    const seen: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts: any) => {
      seen.push({ url, body: opts.body }); return { ok: true, json: async () => ({}) } as any
    }))
    await reclassifyArtist('danbooru', '1', { clothing: ['suit'] })
    expect(seen[0].url).toBe('/api/cf/artist/reclassify?source=danbooru&key=1')
    expect(JSON.parse(seen[0].body)).toEqual({ keep: { clothing: ['suit'] } })
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/__tests__/characterfinder.test.ts`
Expected: FAIL（模块不存在，无法 import）

- [ ] **Step 3: 实现 `frontend/src/api/characterfinder.ts`**

```typescript
const base = ''

// ===== 类型 =====
export interface CfCategoryView { tags: string[]; phrase: string; user_edited: boolean }
export interface CfListItem {
  entry_key: string; source: string; name: string | null; series: string | null
  favorite: boolean
  // 角色
  trigger?: string; core_tags?: string; thumb_url?: string; image_url?: string
  // 艺术家
  tag?: string; thumb1_url?: string; thumb2_url?: string
}
export interface CfSaveBody {
  categories: Record<string, CfCategoryView>
  extras: CfCategoryView
  custom_tags: string[]
}
export interface CfDetail extends CfListItem {
  locked_tags: string[]
  categories: Record<string, CfCategoryView>
  extras: CfCategoryView
  custom_tags: string[]
  model: string; gen_threshold: number; char_threshold: number
  image_override: string | null
}

// entry_key = "{kind}:{source}:{key}"。key 可能含冒号（罕见），故只切前两段。
export function parseEntryKey(ek: string): { kind: string; source: string; key: string } {
  const parts = ek.split(':')
  return { kind: parts[0], source: parts[1], key: parts.slice(2).join(':') }
}

export function cfAssetUrl(kind: string, source: string, key: string, which: string): string {
  const q = new URLSearchParams({ kind, source, key, which })
  return `${base}/api/cf/asset?${q}`
}

function cfQuery(source: string, key: string): string {
  return `source=${encodeURIComponent(source)}&key=${encodeURIComponent(key)}`
}

// ===== 角色 =====
export async function searchCharacters(
  query: string, source: string, series?: string, page = 1, size = 50,
): Promise<{ items: CfListItem[]; total: number }> {
  const q = new URLSearchParams({ query, source, page: String(page), size: String(size) })
  if (series) q.set('series', series)
  return fetch(`${base}/api/cf/characters?${q}`).then(r => r.json())
}

export async function listCharacterSeries(source: string): Promise<{ series: string; count: number }[]> {
  return fetch(`${base}/api/cf/characters/series?source=${encodeURIComponent(source)}`).then(r => r.json())
}

export async function getCharacter(source: string, key: string): Promise<CfDetail> {
  return fetch(`${base}/api/cf/character?${cfQuery(source, key)}`).then(r => r.json())
}

export async function tagCharacter(source: string, key: string, gen_th = 0.35, char_th = 0.9, model = 'wd14'): Promise<CfDetail> {
  return fetch(`${base}/api/cf/character/tag?${cfQuery(source, key)}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model, gen_th, char_th, use_char: true }),
  }).then(r => r.json())
}

export async function reclassifyCharacter(source: string, key: string, keep: Record<string, string[]>): Promise<CfDetail> {
  return fetch(`${base}/api/cf/character/reclassify?${cfQuery(source, key)}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keep }),
  }).then(r => r.json())
}

export async function saveCharacter(source: string, key: string, body: CfSaveBody): Promise<CfDetail> {
  return fetch(`${base}/api/cf/character?${cfQuery(source, key)}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),  // 只含 categories/extras/custom_tags，无 locked_tags
  }).then(r => r.json())
}

export async function uploadCharacterImage(source: string, key: string, file: File): Promise<{ image_override: string }> {
  const fd = new FormData()
  fd.append('file', file)
  return fetch(`${base}/api/cf/character/image?${cfQuery(source, key)}`, { method: 'POST', body: fd }).then(r => r.json())
}

export async function toggleCharacterFavorite(source: string, key: string): Promise<{ favorite: boolean }> {
  return fetch(`${base}/api/cf/character/favorite?${cfQuery(source, key)}`, { method: 'POST' }).then(r => r.json())
}

// ===== 艺术家（同构，路径单数 artist / 复数 artists） =====
export async function searchArtists(
  query: string, source: string, page = 1, size = 50,
): Promise<{ items: CfListItem[]; total: number }> {
  const q = new URLSearchParams({ query, source, page: String(page), size: String(size) })
  return fetch(`${base}/api/cf/artists?${q}`).then(r => r.json())
}

export async function getArtist(source: string, key: string): Promise<CfDetail> {
  return fetch(`${base}/api/cf/artist?${cfQuery(source, key)}`).then(r => r.json())
}

export async function tagArtist(source: string, key: string, gen_th = 0.35, char_th = 0.9, model = 'wd14'): Promise<CfDetail> {
  return fetch(`${base}/api/cf/artist/tag?${cfQuery(source, key)}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model, gen_th, char_th, use_char: true }),
  }).then(r => r.json())
}

export async function reclassifyArtist(source: string, key: string, keep: Record<string, string[]>): Promise<CfDetail> {
  return fetch(`${base}/api/cf/artist/reclassify?${cfQuery(source, key)}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keep }),
  }).then(r => r.json())
}

export async function saveArtist(source: string, key: string, body: CfSaveBody): Promise<CfDetail> {
  return fetch(`${base}/api/cf/artist?${cfQuery(source, key)}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(r => r.json())
}

export async function uploadArtistImage(source: string, key: string, file: File): Promise<{ image_override: string }> {
  const fd = new FormData()
  fd.append('file', file)
  return fetch(`${base}/api/cf/artist/image?${cfQuery(source, key)}`, { method: 'POST', body: fd }).then(r => r.json())
}

export async function toggleArtistFavorite(source: string, key: string): Promise<{ favorite: boolean }> {
  return fetch(`${base}/api/cf/artist/favorite?${cfQuery(source, key)}`, { method: 'POST' }).then(r => r.json())
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npx vitest run src/__tests__/characterfinder.test.ts`
Expected: PASS（全部 describe 通过）

- [ ] **Step 5: 类型检查 + 全量前端测试回归**

Run: `cd frontend && npm run build && npx vitest run`
Expected: build 成功（vue-tsc 无类型错误）；现有测试全绿 + 新增测试通过。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/api/characterfinder.ts frontend/src/__tests__/characterfinder.test.ts
git commit -m "feat(cf): add characterfinder api client (parseEntryKey/cfAssetUrl + char/artist endpoints)"
```

---

### Task 2: detail-utils 加 `buildPromptWithLocked`（锁定标签前置）

**Files:**
- Modify: `frontend/src/detail-utils.ts`（末尾追加导出函数，不改 `buildPrompt`/`parsePhrase`）
- Test: `frontend/src/__tests__/detail.test.ts`（追加 describe，现有 3 个 buildPrompt + 3 个 parsePhrase 用例不动）

**Interfaces:**
- Consumes: `buildPrompt(meta)`（同文件现有）
- Produces: `buildPromptWithLocked(meta, lockedTags?)` → 字符串，锁定标签在最前

**锁定语义**：角色/艺术家详情页复制 prompt 时，权威 `locked_tags`（trigger+core_tags / 画师 tag）必须**始终前置、不可被覆盖层移除**。本函数只做"前置拼接"，不改写 `buildPrompt`（图库 `DetailPage` 仍调 `buildPrompt(meta)` 不受影响）。

- [ ] **Step 1: 写失败测试**

在 `frontend/src/__tests__/detail.test.ts` 末尾追加（不动现有用例）：
```typescript
import { buildPromptWithLocked } from '../detail-utils'

describe('buildPromptWithLocked', () => {
  const meta = { categories: {
    quality: { tags: ['masterpiece'] }, head: { tags: ['long hair'] },
    clothing: { tags: ['dress'] }, view: { tags: [] }, action: { tags: [] }, scene: { tags: [] },
  } }

  it('锁定标签前置在 6 类 prompt 之前', () => {
    expect(buildPromptWithLocked(meta, ['miku', 'vocaloid']))
      .toBe('miku, vocaloid, masterpiece, long hair, dress')
  })
  it('不传 lockedTags 时等价于 buildPrompt', () => {
    expect(buildPromptWithLocked(meta)).toBe('masterpiece, long hair, dress')
  })
  it('空 lockedTags 数组等价于不传', () => {
    expect(buildPromptWithLocked(meta, [])).toBe('masterpiece, long hair, dress')
  })
  it('过滤 lockedTags 内的空串', () => {
    expect(buildPromptWithLocked(meta, ['miku', '']))
      .toBe('miku, masterpiece, long hair, dress')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/__tests__/detail.test.ts`
Expected: FAIL（`buildPromptWithLocked` 未导出）

- [ ] **Step 3: 实现**

在 `frontend/src/detail-utils.ts` **末尾**追加（不改上面的 `buildPrompt`/`parsePhrase`）：
```typescript
// 角色/艺术家详情页用：权威 locked_tags（trigger+core_tags / 画师 tag）始终前置、不可移除。
// 锁定标签来自后端只读数据，覆盖层编辑绝不触碰；拼接时去空串。
export function buildPromptWithLocked(meta: any, lockedTags: string[] = []): string {
  const head = (lockedTags || []).filter(Boolean).join(', ')
  const base = buildPrompt(meta)
  return [head, base].filter(Boolean).join(', ')
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npx vitest run src/__tests__/detail.test.ts`
Expected: PASS（现有 6 + 新增 4 全绿）

- [ ] **Step 5: 提交**

```bash
git add frontend/src/detail-utils.ts frontend/src/__tests__/detail.test.ts
git commit -m "feat(cf): add buildPromptWithLocked (locked tags always prefixed)"
```

---

### Task 3: ImageCard 通用化（向后兼容可选 props + 收藏按钮）

**Files:**
- Modify: `frontend/src/components/ImageCard.vue`
- Test: `frontend/src/__tests__/ImageCard.test.ts`

**Interfaces:**
- Consumes: 现有 `fileUrl`、icons（新增 `IconStar`）
- Produces: 可选 props `to/imgSrc/titleText/tagsList/copyText/downloadSrc/downloadName/favorite` + emit `toggle-favorite`；不传 = 现有行为（图库 `<ImageCard :item/>` 不受影响）

**约束**：现有 `ImageCard.test.ts` 5 个用例（复制/下载按钮、clipboard、tags 前3+N、无 tags 不渲染）必须继续全绿。新增用例覆盖可选 props 与收藏按钮。

- [ ] **Step 1: 改造现有测试的 router mock + 追加新用例**

修改 `frontend/src/__tests__/ImageCard.test.ts`：把顶部的 `vi.mock('vue-router', ...)` 改为模块级 `push`（现有用例不依赖 push，改造无副作用），并在 import 加入 `IconStar`，再追加新 describe：

把文件顶部：
```typescript
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
```
改为：
```typescript
const push = vi.fn()
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))
```
并在每个测试的 `beforeEach(() => { vi.unstubAllGlobals() })` 里加 `push.mockClear()`（现有 describe 的 beforeEach 已存在，只追加这一行）。

在文件末尾追加新 describe（`IconStar` 由 icons 透传，stub 的 NButton 渲染 title，无需额外 mock）：
```typescript
describe('ImageCard 通用化', () => {
  beforeEach(() => { vi.unstubAllGlobals(); push.mockClear() })

  it('传 to 时点击跳转到 to（而非默认 /detail/{id}）', async () => {
    const w = mount(ImageCard, { props: { item: { id: 'x' }, to: '/characters/danbooru/1' } })
    await w.find('.thumb').trigger('click')
    expect(push).toHaveBeenCalledWith('/characters/danbooru/1')
  })
  it('不传 to 时回退到 /detail/{id}', async () => {
    const w = mount(ImageCard, { props: { item: { id: 'abc' } } })
    await w.find('.thumb').trigger('click')
    expect(push).toHaveBeenCalledWith('/detail/abc')
  })
  it('传 imgSrc/titleText/tagsList 时覆盖默认字段', () => {
    const w = mount(ImageCard, {
      props: { item: {}, imgSrc: '/img/a.jpg', titleText: '初音', tagsList: ['1girl', 'singer', 'blue'] },
    })
    expect(w.find('.name').text()).toBe('初音')
    expect(w.findAll('.n-tag').map(t => t.text())).toEqual(['1girl', 'singer', 'blue'])
  })
  it('不传 favorite 时不渲染收藏按钮', () => {
    const w = mount(ImageCard, { props: { item: { id: 'x' } } })
    expect(w.findAll('button').some(b => b.attributes('title') === '收藏')).toBe(false)
  })
  it('传 favorite 时渲染收藏按钮，点击 emit toggle-favorite', async () => {
    const w = mount(ImageCard, { props: { item: { id: 'x' }, favorite: true } })
    const fav = w.findAll('button').find(b => b.attributes('title') === '收藏')!
    expect(fav).toBeTruthy()
    await fav.trigger('click')
    expect(w.emitted('toggle-favorite')).toBeTruthy()
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/__tests__/ImageCard.test.ts`
Expected: FAIL（新 describe：to/imgSrc/favorite 等行为尚未实现）

- [ ] **Step 3: 实现 ImageCard 通用化**

替换 `frontend/src/components/ImageCard.vue` 全文为：
```vue
<script setup lang="ts">
import { computed } from 'vue'
import { NCard, NImage, NButton, NTag, useMessage } from 'naive-ui'
import { useRouter } from 'vue-router'
import { fileUrl } from '../api/client'
import { IconCopy, IconDownload, IconStar } from '../components/icons'

// 通用化：cf 列表（角色/艺术家）与图库共用本卡片。所有覆盖字段为可选，
// 不传时回退到图库 item 的原字段，保证 <ImageCard :item="it" /> 行为完全不变。
const props = defineProps<{
  item: any
  to?: string
  imgSrc?: string
  titleText?: string
  tagsList?: string[]
  copyText?: string
  downloadSrc?: string
  downloadName?: string
  favorite?: boolean
}>()
const emit = defineEmits<{ (e: 'toggle-favorite'): void }>()

const router = useRouter()
const msg = useMessage()

const dest = computed(() => props.to ?? '/detail/' + props.item.id)
const src = computed(() => props.imgSrc ?? fileUrl(props.item.id, props.item.thumb))
const title = computed(() => props.titleText ?? props.item.source_name)
const tags = computed<any[]>(() => props.tagsList ?? props.item.tags ?? [])
const promptForCopy = computed(() => props.copyText ?? props.item.prompt)
const dlSrc = computed(() => props.downloadSrc ?? fileUrl(props.item.id, props.item.original))
const dlName = computed(() => props.downloadName ?? props.item.source_name)
const showFav = computed(() => props.favorite !== undefined)

const showTags = computed(() => tags.value.slice(0, 3))
const moreCount = computed(() => Math.max(0, tags.value.length - 3))

function open() { router.push(dest.value) }
async function copy() {
  const p = promptForCopy.value || ''
  if (!p) { msg.warning('该图尚未反推'); return }
  try { await navigator.clipboard.writeText(p); msg.success('已复制 prompt') }
  catch { msg.error('复制失败') }
}
function download() {
  const a = document.createElement('a')
  a.href = dlSrc.value
  a.download = dlName.value
  document.body.appendChild(a); a.click(); document.body.removeChild(a)
}
</script>

<template>
  <n-card size="small" class="card">
    <div class="thumb" @click="open">
      <n-image :src="src" object-fit="contain" preview-disabled />
      <div class="actions">
        <n-button size="tiny" circle secondary @click.stop="copy" title="复制完整 prompt"><IconCopy/></n-button>
        <n-button size="tiny" circle secondary @click.stop="download" title="下载原图"><IconDownload/></n-button>
      </div>
      <n-button v-if="showFav" size="tiny" circle class="fav-btn"
                :type="favorite ? 'warning' : 'default'"
                @click.stop="emit('toggle-favorite')" title="收藏"><IconStar/></n-button>
    </div>
    <div class="name">{{ title }}</div>
    <div v-if="showTags.length" class="tags">
      <n-tag v-for="t in showTags" :key="t" size="tiny" round>{{ t }}</n-tag>
      <n-tag v-if="moreCount" size="tiny" round :bordered="false" type="info">+{{ moreCount }}</n-tag>
    </div>
  </n-card>
</template>

<style scoped>
.thumb { position: relative; cursor: pointer }
.actions { position: absolute; left: 6px; top: 6px; display: flex; gap: 4px }
.actions :deep(.n-button) { box-shadow: 0 2px 6px rgba(0, 0, 0, 0.45) }
.fav-btn { position: absolute; right: 6px; top: 6px; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.45) }
.name {
  font-size: 12px; margin-top: 4px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.tags { display: flex; flex-wrap: wrap; gap: 3px; margin-top: 4px }
.tags :deep(.n-tag) { font-size: 11px }
.card { transition: transform .2s ease, box-shadow .2s ease }
.card:hover { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(0, 0, 0, 0.12) }
.actions :deep(.n-button) { color: inherit }
:deep(.n-image) { display: block; width: 100%; height: 160px }
:deep(.n-image img) { width: 100%; height: 100%; object-fit: contain; display: block }
</style>
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npx vitest run src/__tests__/ImageCard.test.ts`
Expected: PASS（原 5 + 新 5 全绿）

- [ ] **Step 5: 回归图库（确认向后兼容）**

Run: `cd frontend && npx vitest run src/__tests__/GalleryPage.test.ts`
Expected: PASS（图库未受通用化影响）

- [ ] **Step 6: 提交**

```bash
git add frontend/src/components/ImageCard.vue frontend/src/__tests__/ImageCard.test.ts
git commit -m "feat(cf): generalize ImageCard with optional to/imgSrc/title/tags/favorite props"
```

---

### Task 4: TagEditor 加 `lockedTags`（只读 🔒 chip）

**Files:**
- Modify: `frontend/src/components/TagEditor.vue`
- Test: `frontend/src/__tests__/TagEditor.test.ts`

**Interfaces:**
- Consumes: 现有 `modelValue`/`mode`/`categoryKey`
- Produces: 可选 prop `lockedTags?: string[]`；不传 = 无锁区（现有详情页不受影响）。锁区 chip 带 class `locked-tag`、不可关闭、不参与增删/拖拽。

- [ ] **Step 1: 写失败测试**

在 `frontend/src/__tests__/TagEditor.test.ts` 末尾追加（现有 3 个用例不动）：
```typescript
describe('TagEditor lockedTags', () => {
  beforeEach(() => vi.unstubAllGlobals())

  it('传 lockedTags 时渲染只读锁定标签（带 locked-tag 类，不可关闭）', () => {
    const w = mount(TagEditor, {
      props: {
        title: '角色头部', color: '#4CAF50',
        modelValue: MODEL(['long hair']), mode: 'tags', categoryKey: 'head',
        lockedTags: ['miku', 'vocaloid'],
      },
    })
    const locked = w.findAll('.locked-tag')
    expect(locked.length).toBe(2)
    expect(locked.map(t => t.text())).toEqual(['miku', 'vocaloid'])
  })
  it('不传 lockedTags 时不渲染锁定标签', () => {
    const w = mount(TagEditor, {
      props: { title: '角色头部', color: '#4CAF50', modelValue: MODEL(['long hair']), mode: 'tags', categoryKey: 'head' },
    })
    expect(w.findAll('.locked-tag').length).toBe(0)
  })
  it('锁定标签不进入可编辑 tags（增删/拖拽不影响锁区）', () => {
    const w = mount(TagEditor, {
      props: {
        title: '角色头部', color: '#4CAF50',
        modelValue: MODEL(['long hair']), mode: 'tags', categoryKey: 'head',
        lockedTags: ['miku'],
      },
    })
    // 可编辑区 n-tag 不含 miku（锁区单独渲染）
    const editable = w.findAll('.n-tag').filter(t => !t.classes().includes('locked-tag'))
    expect(editable.map(t => t.text())).toEqual(['long hair'])
  })
})
```

> 注意：现有测试 mock 的 `NTag` 是 `<span class="n-tag"><slot/></span>`。锁区也用 `n-tag` 但额外加 class `locked-tag`；测试靠 `.locked-tag` 类区分。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/__tests__/TagEditor.test.ts`
Expected: FAIL（`.locked-tag` 不存在）

- [ ] **Step 3: 实现**

在 `frontend/src/components/TagEditor.vue` 的 `defineProps` 块加一个可选字段（其余 props/emit 不变）：
```typescript
const props = defineProps<{
  title: string; color: string
  modelValue: { tags: string[]; phrase: string; user_edited: boolean }
  mode: 'tags' | 'phrase'
  categoryKey?: string
  lockedTags?: string[]
}>()
```

在 `<template>` 的 `<div class="cat-body">` 内、`<template v-if="mode === 'tags'">` **之前**插入锁区（仅 tags 模式显示；短语模式无锁区）：
```html
      <!-- 🔒 锁定标签：来自权威数据（角色 trigger+core_tags / 画师 tag），只读不可增删/拖拽 -->
      <div v-if="lockedTags && lockedTags.length && mode === 'tags'" class="locked-tags">
        <n-tag v-for="t in lockedTags" :key="'lock-' + t" class="locked-tag" size="small" round :bordered="false" type="warning">
          🔒 {{ t }}
        </n-tag>
      </div>
```

在 `<style scoped>` 末尾追加：
```css
.locked-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npx vitest run src/__tests__/TagEditor.test.ts`
Expected: PASS（原 3 + 新 3 全绿）

- [ ] **Step 5: 回归详情页（确认向后兼容）**

Run: `cd frontend && npx vitest run src/__tests__/PromptboxDetailPage.test.ts src/__tests__/DetailPage.test.ts 2>/dev/null; npx vitest run src/__tests__/PromptboxDetailPage.test.ts`
Expected: PASS（现有详情页不传 lockedTags，无锁区，行为不变）

- [ ] **Step 6: 提交**

```bash
git add frontend/src/components/TagEditor.vue frontend/src/__tests__/TagEditor.test.ts
git commit -m "feat(cf): add read-only lockedTags chips to TagEditor"
```

---

### Task 5: icons + router + App 导航注册

**Files:**
- Modify: `frontend/src/components/icons.ts`（加 `IconCharacter`/`IconArtist`）
- Modify: `frontend/src/router.ts`（加 4 条路由）
- Modify: `frontend/src/App.vue`（`ITEMS` 加 2 项 + `currentTitle` 详情特判）
- Test: `frontend/src/__tests__/icons.test.ts`（补新 icon 断言）、新建 `frontend/src/__tests__/router.test.ts`、`frontend/src/__tests__/App.test.ts`（加标题 case）

**Interfaces:**
- Consumes: Task 1-4 的客户端/组件（路由组件在 Task 6-8 创建；本 task 先注册路由 import，但组件文件需先存在才能 build——**因此 Task 5 的 router 改动依赖 Task 6-8 的页面文件存在**。执行顺序：Task 6-8 创建页面 → Task 5 注册路由。或 Task 5 先建路由但暂用占位——**采用：Task 6/7/8 先建页面组件，Task 5 最后接线注册**。下文 Step 顺序已按此安排。）

> **执行顺序调整**：本 task 的 `router.ts`/`App.vue` import 了 `CharactersPage` 等尚未存在的组件，若在 Task 6-8 之前执行会导致 build 失败。因此 **Task 5 拆为两段**：5a（icons，独立可测，先做）在 Task 6 之前；5b（router+App 接线）在 Task 8 之后做。下文给出完整步骤，执行时 5a 插在 Task 4 之后、5b 放在 Task 8 之后。

#### 5a: icons（独立，先做）

- [ ] **Step 1: 写失败测试**

在 `frontend/src/__tests__/icons.test.ts` 末尾追加（先读该文件确认现有断言风格——通常断言 icon 是 functional component；按其风格补）：
```typescript
import { IconCharacter, IconArtist } from '../components/icons'

describe('cf icons', () => {
  it('IconCharacter / IconArtist 已导出且为功能组件', () => {
    expect(IconCharacter).toBeTruthy()
    expect(IconArtist).toBeTruthy()
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/__tests__/icons.test.ts`
Expected: FAIL（未导出）

- [ ] **Step 3: 实现**

在 `frontend/src/components/icons.ts` 末尾追加（沿用现有 `I(() => [h(...)])` 范式）：
```typescript
export const IconCharacter = I(() => [
  h('circle', { cx: 12, cy: 8, r: 4 }),
  h('path', { d: 'M4 21a8 8 0 0 1 16 0' }),
])
export const IconArtist = I(() => [
  // 调色板
  h('path', { d: 'M12 2a10 10 0 1 0 0 20 2 2 0 0 0 2-2 2 2 0 0 1 2-2h2a6 6 0 0 0 6-6 10 10 0 0 0-12-10z' }),
  h('circle', { cx: 7.5, cy: 10.5, r: 1.2, fill: 'currentColor', stroke: 'none' }),
  h('circle', { cx: 12, cy: 7.5, r: 1.2, fill: 'currentColor', stroke: 'none' }),
  h('circle', { cx: 16.5, cy: 10.5, r: 1.2, fill: 'currentColor', stroke: 'none' }),
])
```

- [ ] **Step 4: 跑测试确认通过 + 提交**

Run: `cd frontend && npx vitest run src/__tests__/icons.test.ts` → PASS
```bash
git add frontend/src/components/icons.ts frontend/src/__tests__/icons.test.ts
git commit -m "feat(cf): add IconCharacter/IconArtist"
```

---

### Task 6: CharactersPage 角色列表页

**Files:**
- Create: `frontend/src/views/CharactersPage.vue`
- Test: `frontend/src/__tests__/CharactersPage.test.ts`

**Interfaces:**
- Consumes: Task 1 `searchCharacters`/`listCharacterSeries`/`parseEntryKey`/`toggleCharacterFavorite`/`CfListItem`；Task 3 通用化 `ImageCard`
- Produces: 角色列表页（筛选：来源/系列/搜索；网格复用 ImageCard；收藏 toggle）

**设计决策（后端现实）**：P1 后端 `search_characters` 只支持 `query/source/series/page/size`（无 `favorite_only`）。故列表页筛选为这三项；收藏仅做卡片状态展示 + toggle（点星标调 `toggleCharacterFavorite` 并就地刷新 `item.favorite`）。"只看收藏"列表留待 P3 的 `/api/cf/favorites` 页。

- [ ] **Step 1: 写失败测试**

Create `frontend/src/__tests__/CharactersPage.test.ts`:
```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import CharactersPage from '../views/CharactersPage.vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('naive-ui', async () => {
  const actual: any = await vi.importActual('naive-ui')
  return { ...actual, useMessage: () => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn() }) }
})

describe('CharactersPage', () => {
  beforeEach(() => vi.unstubAllGlobals())

  it('渲染筛选栏（来源/系列/搜索）', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ items: [], total: 0 }) }) as any))
    const w = mount(CharactersPage, { global: { stubs: { NImage: true } } })
    await flushPromises()
    expect(w.find('.filter-bar').exists()).toBe(true)
    const labels = w.find('.filter-bar').text()
    expect(labels).toContain('来源')
    expect(labels).toContain('系列')
    expect(labels).toContain('搜索')
  })

  it('加载角色列表并请求 /api/cf/characters?source=danbooru，渲染卡片名称', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url)
      if (url.includes('/characters/series')) return { ok: true, json: async () => [{ series: 'vocaloid', count: 3 }] } as any
      return { ok: true, json: async () => ({ items: [{ entry_key: 'char:danbooru:1', source: 'danbooru', name: 'miku', series: 'vocaloid', core_tags: 'miku, 1girl', favorite: false }], total: 1 }) } as any
    }))
    const w = mount(CharactersPage, { global: { stubs: { NImage: true } } })
    await flushPromises()
    expect(urls.some(u => u.includes('/api/cf/characters?') && u.includes('source=danbooru'))).toBe(true)
    expect(w.text()).toContain('miku')
  })

  it('切换来源触发重新加载并清空 series', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url)
      if (url.includes('/characters/series')) return { ok: true, json: async () => [] } as any
      return { ok: true, json: async () => ({ items: [], total: 0 }) } as any
    }))
    const w = mount(CharactersPage, { global: { stubs: { NImage: true } } })
    await flushPromises()
    urls.length = 0
    ;(w.vm as any).onSource('anima')
    await flushPromises()
    expect(urls.some(u => u.includes('source=anima'))).toBe(true)
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/__tests__/CharactersPage.test.ts`
Expected: FAIL（组件不存在）

- [ ] **Step 3: 实现 `frontend/src/views/CharactersPage.vue`**

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NCard, NGrid, NGridItem, NPagination, NEmpty, NSelect, NInput } from 'naive-ui'
import {
  searchCharacters, listCharacterSeries, toggleCharacterFavorite, parseEntryKey,
  type CfListItem,
} from '../api/characterfinder'
import ImageCard from '../components/ImageCard.vue'

const items = ref<CfListItem[]>([])
const total = ref(0)
const page = ref(1)
const size = 50
const query = ref('')
const source = ref('danbooru')
const series = ref<string | null>(null)
const seriesOptions = ref<{ label: string; value: string }[]>([])

const SOURCE_OPTIONS = [
  { label: 'Danbooru', value: 'danbooru' },
  { label: 'e621', value: 'e621' },
  { label: 'Anima', value: 'anima' },
]

async function load() {
  const r = await searchCharacters(query.value, source.value, series.value || undefined, page.value, size)
  items.value = r.items; total.value = r.total
}
async function loadSeries() {
  const list = await listCharacterSeries(source.value)
  seriesOptions.value = list.map(s => ({ label: `${s.series} (${s.count})`, value: s.series }))
}
onMounted(() => { load(); loadSeries() })

function onSource(v: string) {
  source.value = v; page.value = 1; series.value = null
  load(); loadSeries()
}
function onSeries(v: string | null) { series.value = v; page.value = 1; load() }

// 防抖 350ms；回车立即
let queryTimer: any = null
function onQuery(v: string) {
  query.value = v
  clearTimeout(queryTimer)
  queryTimer = setTimeout(() => { page.value = 1; load() }, 350)
}
function onQueryEnter() { clearTimeout(queryTimer); page.value = 1; load() }

// cf item → 通用化 ImageCard 的 props 映射
function cardTo(it: CfListItem): string {
  const { source: s, key } = parseEntryKey(it.entry_key)
  return `/characters/${s}/${encodeURIComponent(key)}`
}
function cardImg(it: CfListItem): string {
  return it.thumb_url || ''
}
function cardTags(it: CfListItem): string[] {
  const raw = it.core_tags || it.tag || ''
  return raw.split(',').map(t => t.trim()).filter(Boolean)
}
async function onToggleFav(it: CfListItem) {
  const { source: s, key } = parseEntryKey(it.entry_key)
  try {
    const r = await toggleCharacterFavorite(s, key)
    it.favorite = r.favorite
  } catch { /* 静默：列表态不弹错 */ }
}
</script>

<template>
  <n-card size="small" class="filter-bar" style="margin-bottom:16px">
    <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">
      <div class="field"><span class="field-label">来源</span>
        <n-select :value="source" :options="SOURCE_OPTIONS" size="small" style="width:140px"
                  @update:value="onSource" /></div>
      <div class="field"><span class="field-label">系列</span>
        <n-select :value="series" :options="seriesOptions" clearable filterable size="small"
                  placeholder="全部系列" style="min-width:220px;max-width:320px"
                  @update:value="onSeries" /></div>
      <div class="field"><span class="field-label">搜索</span>
        <n-input :value="query" placeholder="名称 / 触发词" size="small" clearable
                 @update:value="onQuery" @keyup.enter="onQueryEnter"
                 style="min-width:220px;max-width:300px" /></div>
    </div>
  </n-card>
  <n-empty v-if="!items.length" description="没有符合条件的角色" />
  <n-grid v-else cols="2 600:3 900:5 1200:6" :x-gap="12" :y-gap="12">
    <n-grid-item v-for="it in items" :key="it.entry_key">
      <ImageCard :item="it" :to="cardTo(it)" :img-src="cardImg(it)"
                 :title-text="it.name || ''" :tags-list="cardTags(it)"
                 :favorite="it.favorite" @toggle-favorite="onToggleFav(it)" />
    </n-grid-item>
  </n-grid>
  <n-pagination v-if="total > size" v-model:page="page" :item-count="total"
                :page-size="size" @update:page="load" style="margin-top:16px" />
</template>

<style scoped>
.field { display: flex; align-items: center; gap: 8px }
.field-label { font-size: 13px; font-weight: 600; color: var(--n-text-color-3, #6b7280); min-width: 28px }
</style>
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npx vitest run src/__tests__/CharactersPage.test.ts`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/CharactersPage.vue frontend/src/__tests__/CharactersPage.test.ts
git commit -m "feat(cf): add CharactersPage list (source/series/search + ImageCard reuse)"
```

---

### Task 7: CharacterDetailPage 角色详情页

**Files:**
- Create: `frontend/src/views/CharacterDetailPage.vue`
- Test: `frontend/src/__tests__/CharacterDetailPage.test.ts`

**Interfaces:**
- Consumes: Task 1 `getCharacter`/`tagCharacter`/`reclassifyCharacter`/`saveCharacter`/`uploadCharacterImage`/`toggleCharacterFavorite`/`CfDetail`；Task 2 `buildPromptWithLocked`；`TagEditor`；`useTagger`
- Produces: 角色详情编辑页（双栏 + 顶部 🔒 锁定标签区 + 反推/重分类/保存/换图/收藏/复制 prompt）

**设计要点**：
- 后端 detail 的 `categories`/`extras` 已是 `{tags,phrase,user_edited}` 形状（与 TagEditor modelValue 同构），**无需包/拆**（区别于 PromptboxDetailPage 那样在 string[] 与 CatView 间转换）。save body 直接传 `detail.categories/extras/custom_tags`。
- **🔒 锁定标签**：`detail.locked_tags`（trigger+core_tags）在右栏顶部**独立锁区**渲染（跨所有类，不属于单个 TagEditor）。与 TagEditor.lockedTags（Task 4，分类级锁定能力，设计 §5.5 mandated）共用 `.locked-tag` 视觉风格；本页因 locked_tags 跨类故用顶部独立区。
- `fullPrompt = buildPromptWithLocked(detail, detail.locked_tags)`：锁定标签始终前置。
- 图片走 `detail.image_url`（后端已拼 `/api/cf/asset`）；换图后用 `imgVersion` cache-buster 强制刷新。

- [ ] **Step 1: 写失败测试**

Create `frontend/src/__tests__/CharacterDetailPage.test.ts`:
```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import CharacterDetailPage from '../views/CharacterDetailPage.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { source: 'danbooru', key: '1' } }),
  useRouter: () => ({ push: vi.fn() }),
}))
vi.mock('naive-ui', async () => {
  const actual: any = await vi.importActual('naive-ui')
  return { ...actual, useMessage: () => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn() }) }
})
vi.mock('../composables/useTagger', () => {
  const state = { selected: 'wd14', taggers: [{ key: 'wd14', label: 'WD14', downloaded: true }], downloading: null }
  return { useTagger: () => ({ state, setSelected: vi.fn(), refresh: vi.fn(async () => {}), isDownloaded: () => true, download: vi.fn(async () => {}) }) }
})

const DETAIL = {
  entry_key: 'char:danbooru:1', source: 'danbooru', name: 'miku', series: 'vocaloid',
  trigger: 'miku', core_tags: 'miku, 1girl',
  thumb_url: '/api/cf/asset?kind=char&source=danbooru&key=1&which=thumb',
  image_url: '/api/cf/asset?kind=char&source=danbooru&key=1&which=image',
  favorite: false, locked_tags: ['miku', '1girl'],
  categories: { head: { tags: ['long hair'], phrase: 'long hair', user_edited: false } },
  extras: { tags: [], phrase: '', user_edited: false },
  custom_tags: [], model: 'wd14', gen_threshold: 0.35, char_threshold: 0.9, image_override: null,
}

describe('CharacterDetailPage', () => {
  beforeEach(() => vi.unstubAllGlobals())

  function stubFetch(handler: (url: string, opts?: any) => any) {
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts?: any) => {
      return { ok: true, json: async () => handler(url, opts) } as any
    }))
  }

  it('加载详情：渲染锁定标签 + 分类标签', async () => {
    stubFetch((url) => { if (url.includes('/api/cf/character?')) return DETAIL; return {} })
    const w = mount(CharacterDetailPage, { global: { stubs: { NImage: true, NUpload: true } } })
    await flushPromises()
    const locked = w.findAll('.locked-tag').map(t => t.text())
    expect(locked).toContain('🔒 miku')
    expect(locked).toContain('🔒 1girl')
    expect(w.text()).toContain('long hair')
  })

  it('save 的 PUT body 含 categories/extras/custom_tags，不含 locked_tags', async () => {
    const seen: any[] = []
    stubFetch((url, opts) => {
      if (url.includes('/api/cf/character?') && opts && opts.method === 'PUT') seen.push(opts.body)
      if (url.includes('/api/cf/character?')) return DETAIL
      return {}
    })
    const w = mount(CharacterDetailPage, { global: { stubs: { NImage: true, NUpload: true } } })
    await flushPromises()
    await (w.vm as any).save()
    await flushPromises()
    expect(seen.length).toBe(1)
    const body = JSON.parse(seen[0])
    expect(body.categories).toBeTruthy()
    expect(body.custom_tags).toEqual([])
    expect(body.locked_tags).toBeUndefined()
  })

  it('反推调 /api/cf/character/tag', async () => {
    const urls: string[] = []
    stubFetch((url) => {
      if (url.includes('/api/cf/character/tag')) { urls.push(url); return DETAIL }
      if (url.includes('/api/cf/character?')) return DETAIL
      return {}
    })
    const w = mount(CharacterDetailPage, { global: { stubs: { NImage: true, NUpload: true } } })
    await flushPromises()
    await (w.vm as any).reTag()
    await flushPromises()
    expect(urls.some(u => u.includes('/api/cf/character/tag?source=danbooru&key=1'))).toBe(true)
  })

  it('换图 POST FormData 到 /api/cf/character/image', async () => {
    const seen: any[] = []
    stubFetch((url, opts) => {
      if (url.includes('/api/cf/character/image')) { seen.push({ url, body: opts?.body }); return { image_override: 'new.png' } }
      if (url.includes('/api/cf/character?')) return DETAIL
      return {}
    })
    const w = mount(CharacterDetailPage, { global: { stubs: { NImage: true, NUpload: true } } })
    await flushPromises()
    await (w.vm as any).uploadImage(new File(['x'], 'up.png', { type: 'image/png' }))
    await flushPromises()
    expect(seen[0].url).toContain('/api/cf/character/image?source=danbooru&key=1')
    expect(seen[0].body).toBeInstanceOf(FormData)
  })

  it('收藏 toggle 调 /api/cf/character/favorite', async () => {
    const urls: string[] = []
    stubFetch((url) => {
      if (url.includes('/api/cf/character/favorite')) { urls.push(url); return { favorite: true } }
      if (url.includes('/api/cf/character?')) return DETAIL
      return {}
    })
    const w = mount(CharacterDetailPage, { global: { stubs: { NImage: true, NUpload: true } } })
    await flushPromises()
    await (w.vm as any).toggleFav()
    await flushPromises()
    expect(urls.some(u => u.includes('/api/cf/character/favorite?source=danbooru&key=1'))).toBe(true)
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/__tests__/CharacterDetailPage.test.ts`
Expected: FAIL（组件不存在）

- [ ] **Step 3: 实现 `frontend/src/views/CharacterDetailPage.vue`**

```vue
<script setup lang="ts">
import { ref, computed, watch, onMounted, h } from 'vue'
import { useRoute } from 'vue-router'
import {
  NSpace, NButton, NRadioGroup, NRadioButton, NImage, NCard,
  NInputNumber, NInput, NDynamicTags, NTag, NUpload, NSelect,
  useMessage,
} from 'naive-ui'
import TagEditor from '../components/TagEditor.vue'
import {
  getCharacter, tagCharacter, reclassifyCharacter, saveCharacter,
  uploadCharacterImage, toggleCharacterFavorite, type CfDetail,
} from '../api/characterfinder'
import { useTagger } from '../composables/useTagger'
import { buildPromptWithLocked } from '../detail-utils'
import { IconPlus } from '../components/icons'

const tagger = useTagger()
const route = useRoute(); const msg = useMessage()
const source = computed(() => route.params.source as string)
const key = computed(() => route.params.key as string)

const ORDER = ['quality', 'head', 'clothing', 'view', 'action', 'scene'] as const
const KEY_TITLES: [string, string, string][] = [
  ['head', '角色头部', '#4CAF50'], ['clothing', '服装', '#2196F3'],
  ['view', '视角构图', '#9C27B0'], ['action', '动作', '#FF9800'],
  ['scene', '场景', '#795548'], ['quality', '质量词（预设）', '#607D8B'],
]

const detail = ref<CfDetail | null>(null)
const mode = ref<'tags' | 'phrase'>('tags')
const dirty = ref(false)
const genTh = ref(0.35); const charTh = ref(0.9)
const localModel = ref('')
const handEdited = ref<Set<string>>(new Set())
// 换图后强制刷新 <n-image>（asset URL 不变，内容变了）
const imgVersion = ref(0)

const taggerOptions = computed(() => tagger.state.taggers.map(t => ({ label: t.label, value: t.key, downloaded: t.downloaded })))
function renderTaggerLabel(option: any) {
  return h('span', { style: 'display:inline-flex;align-items:center;gap:6px' }, [
    option.label as any,
    option.downloaded ? h(NTag, { type: 'success', size: 'small', bordered: false }, { default: () => '已下载' })
                       : h(NTag, { size: 'small', bordered: false }, { default: () => '未下载' }),
  ])
}
const modelDownloaded = computed(() => tagger.isDownloaded(localModel.value))
onMounted(() => { tagger.refresh() })
async function doDownload() {
  try { await tagger.download(localModel.value); msg.success('下载完成') }
  catch (e: any) { msg.error('下载失败：' + e.message) }
}
const charLabel = computed(() => localModel.value === 'cl_tagger' ? '角色名称识别阈值（仅 cl_tagger 生效）' : '角色')
let modelChangeFromLoad = false
watch(localModel, (m) => {
  if (modelChangeFromLoad) { modelChangeFromLoad = false; return }
  if (m === 'cl_tagger_v2') { genTh.value = 0.55; charTh.value = 0.55 }
  else { charTh.value = m === 'cl_tagger' ? 0.6 : 0.9 }
})

function fromDetail(d: CfDetail) {
  detail.value = d; dirty.value = false; handEdited.value = new Set()
  if (d.model === 'cl_tagger_v2') { genTh.value = 0.55; charTh.value = 0.55 }
  else { genTh.value = d.gen_threshold; charTh.value = d.char_threshold }
  modelChangeFromLoad = true; localModel.value = d.model
}

async function load() {
  const s = source.value, k = key.value
  try {
    const d = await getCharacter(s, k)
    if (s !== source.value || k !== key.value) return  // 已切条目，丢弃旧结果防竞态
    fromDetail(d)
  } catch (e: any) { msg.error('加载失败：' + e.message) }
}
watch([source, key], load, { immediate: true })

// 后端 categories 已是 {k:{tags,phrase,user_edited}}，与 TagEditor modelValue 同构，直接改
function setCat(k: string, val: any) { detail.value!.categories[k] = val; dirty.value = true; if (val.user_edited) handEdited.value.add(k) }
function setExtras(val: any) { detail.value!.extras = val; dirty.value = true }
function onCustomTags(v: string[]) { detail.value!.custom_tags = v; dirty.value = true }
function applyPhrase(k: string, tags: string[]) {
  const next = { tags, phrase: tags.join(', '), user_edited: true }
  if (k === 'extras') setExtras(next); else setCat(k, next)
}

async function save() {
  if (!detail.value) return
  try {
    const d = await saveCharacter(source.value, key.value, {
      categories: detail.value.categories, extras: detail.value.extras, custom_tags: detail.value.custom_tags,
    })
    fromDetail(d); msg.success('已保存')
  } catch (e: any) { msg.error('保存失败：' + e.message) }
}
async function reTag() {
  try {
    const d = await tagCharacter(source.value, key.value, genTh.value, charTh.value, localModel.value)
    fromDetail(d); msg.success('反推完成')
  } catch (e: any) { msg.error('反推失败：' + e.message) }
}
async function reClassify() {
  const keep: Record<string, string[]> = {}
  handEdited.value.forEach(k => { keep[k] = detail.value!.categories[k].tags })
  try {
    const d = await reclassifyCharacter(source.value, key.value, keep)
    fromDetail(d); msg.success('重分类完成（跳过手改类）')
  } catch (e: any) { msg.error('重分类失败：' + e.message) }
}
async function uploadImage(file: File) {
  try {
    const r = await uploadCharacterImage(source.value, key.value, file)
    detail.value!.image_override = r.image_override; imgVersion.value++; msg.success('图片已替换')
  } catch (e: any) { msg.error('上传失败：' + e.message) }
}
function onUploadReq({ file }: any) { const f = (file as any)?.file as File | undefined; if (f) uploadImage(f) }
async function toggleFav() {
  try {
    const r = await toggleCharacterFavorite(source.value, key.value)
    detail.value!.favorite = r.favorite
  } catch (e: any) { msg.error('收藏失败：' + e.message) }
}

const fullPrompt = computed(() => detail.value ? buildPromptWithLocked(detail.value, detail.value.locked_tags) : '')
async function copyPrompt() {
  if (!fullPrompt.value) { msg.warning('暂无提示词'); return }
  try { await navigator.clipboard.writeText(fullPrompt.value); msg.success('已复制完整 prompt') }
  catch { msg.error('复制失败') }
}
const imgSrc = computed(() => detail.value ? detail.value.image_url + (imgVersion.value ? `&_v=${imgVersion.value}` : '') : '')
const hasImage = computed(() => !!imgSrc.value)
</script>

<template>
  <div v-if="detail" style="display:grid;grid-template-columns:minmax(280px,1fr) minmax(0,2fr);gap:16px">
    <div>
      <n-card>
        <div class="img-wrap">
          <n-image v-if="hasImage" :src="imgSrc" :preview-src="imgSrc" object-fit="contain"
                   style="max-height:420px;width:100%;display:block" />
          <div v-else class="no-img">暂无图片</div>
        </div>
        <div style="font-size:12px;margin-top:8px">
          <div style="margin-bottom:4px">
            <span style="font-weight:600">{{ detail.name }}</span>
            <span v-if="detail.series" style="color:var(--n-text-color-3,#888);margin-left:8px">{{ detail.series }}</span>
          </div>
          <div>{{ detail.source }}</div>
          <div style="margin-top:6px">
            <div style="font-size:13px;margin-bottom:4px">反推模型</div>
            <n-select :value="localModel" :options="taggerOptions" :render-label="renderTaggerLabel"
                      @update:value="(v: string) => localModel = v" size="small" style="max-width:260px" />
            <div v-if="!modelDownloaded" style="margin-top:4px;display:flex;align-items:center;gap:6px">
              <span style="font-size:12px;color:#d03050">{{ tagger.state.taggers.find(t=>t.key===localModel)?.label || localModel }} 未下载</span>
              <n-button size="tiny" :loading="tagger.state.downloading===localModel" @click="doDownload">下载</n-button>
            </div>
          </div>
          <div>通用 <n-input-number v-model:value="genTh" :step="0.05" :min="0" :max="1" size="small" style="width:96px" /><template v-if="localModel !== 'cl_tagger_v2'"> / {{ charLabel }} <n-input-number v-model:value="charTh" :step="0.05" :min="0" :max="1" size="small" style="width:96px" /></template></div>
          <div style="margin-top:6px">
            <div style="color:var(--cat-input-color,#888);margin-bottom:2px">自定义标签</div>
            <n-dynamic-tags :value="detail.custom_tags || []" size="small" @update:value="onCustomTags" />
          </div>
        </div>
        <n-space vertical style="margin-top:8px">
          <n-upload :show-file-list="false" :max="1" accept="image/*" :custom-request="onUploadReq">
            <n-button size="small"><IconPlus/> 替换图片</n-button>
          </n-upload>
          <n-button size="small" @click="reTag">重新反推</n-button>
          <n-button size="small" @click="reClassify">重分类</n-button>
          <n-button size="small" @click="copyPrompt">复制完整 prompt</n-button>
          <n-button size="small" :type="detail.favorite ? 'warning' : 'default'" @click="toggleFav">
            {{ detail.favorite ? '★ 已收藏' : '☆ 收藏' }}
          </n-button>
        </n-space>
      </n-card>
    </div>
    <div>
      <!-- 🔒 锁定标签区：权威 trigger+core_tags，只读不可编辑 -->
      <div v-if="detail.locked_tags && detail.locked_tags.length" class="locked-box">
        <span class="locked-title">🔒 锁定标签（权威，不可编辑）</span>
        <div class="locked-tags">
          <n-tag v-for="t in detail.locked_tags" :key="'lock-' + t" class="locked-tag" size="small" round :bordered="false" type="warning">{{ '🔒 ' + t }}</n-tag>
        </div>
      </div>
      <n-space align="center" style="margin-bottom:10px">
        <n-radio-group v-model:value="mode" size="small">
          <n-radio-button value="tags">标签</n-radio-button>
          <n-radio-button value="phrase">短句</n-radio-button>
        </n-radio-group>
        <n-button size="small" type="primary" :disabled="!dirty" @click="save">保存</n-button>
      </n-space>
      <TagEditor v-for="[k, title, color] in KEY_TITLES" :key="k" :title="title" :color="color"
                 :mode="mode" :category-key="k"
                 :model-value="detail.categories[k] || { tags: [], phrase: '', user_edited: false }"
                 @update:modelValue="(v) => setCat(k, v)" @apply-phrase="(t) => applyPhrase(k, t)" />
      <TagEditor title="未归类 extras（拖到各类为复制，不会移除原标签）" color="#9E9E9E" :mode="mode"
                 category-key="extras" :model-value="detail.extras"
                 @update:modelValue="setExtras" @apply-phrase="(t) => applyPhrase('extras', t)" />
    </div>
  </div>
</template>

<style scoped>
:deep(.n-image) { display: block; width: 100% }
:deep(.n-image img) { max-width: 100%; max-height: 420px; width: auto; height: auto; object-fit: contain; display: block; margin: 0 auto }
.img-wrap { border-radius: 10px; padding: 8px; display: flex; align-items: center; justify-content: center }
.no-img { height: 200px; display: flex; align-items: center; justify-content: center; font-size: 13px; border-radius: 4px }
.locked-box { border: 1px dashed #d4a017; border-radius: 8px; padding: 8px 10px; margin-bottom: 12px; background: var(--cat-panel-bg, #fafafa) }
.locked-title { font-size: 12px; font-weight: 600; color: #b8860b; display: block; margin-bottom: 6px }
.locked-tags { display: flex; flex-wrap: wrap; gap: 4px }
</style>
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npx vitest run src/__tests__/CharacterDetailPage.test.ts`
Expected: PASS（5 个用例全绿）

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/CharacterDetailPage.vue frontend/src/__tests__/CharacterDetailPage.test.ts
git commit -m "feat(cf): add CharacterDetailPage (locked tags + tag/reclassify/save/image/favorite)"
```

---

### Task 8: ArtistsPage 列表 + ArtistDetailPage 详情（双图）

**Files:**
- Create: `frontend/src/views/ArtistsPage.vue`
- Create: `frontend/src/views/ArtistDetailPage.vue`
- Test: `frontend/src/__tests__/ArtistsPage.test.ts`
- Test: `frontend/src/__tests__/ArtistDetailPage.test.ts`

**Interfaces:**
- Consumes: Task 1 `searchArtists`/`getArtist`/`tagArtist`/`reclassifyArtist`/`saveArtist`/`uploadArtistImage`/`toggleArtistFavorite`/`parseEntryKey`/`CfDetail`；Task 3 `ImageCard`（通用化）；Task 2 `buildPromptWithLocked`；`TagEditor`；`useTagger`
- Produces: 艺术家列表页（无 series，source+search 筛选）+ 艺术家详情页（**双图** thumb1/thumb2 + 锁定画师 tag）

**差异点（相对角色）**：艺术家**无 series 概念**，列表筛选仅 source + search；详情左栏展示**两张参考图**（thumb1_url/thumb2_url，后端 `_asset(which=1/2)`）；`locked_tags` = 画师 tag 拆词（后端 Task 11 `routes_artists`）。其余反推/重分类/保存/换图/收藏与角色同构。

> **注**：Task 1 定义的 `listArtistSeries` 在 P2 无消费者（艺术家无系列）；执行 Task 1 时可安全省略该函数（YAGNI）。

#### Task 8a: ArtistsPage 列表页

- [ ] **Step 1: 写失败测试**

Create `frontend/src/__tests__/ArtistsPage.test.ts`:
```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ArtistsPage from '../views/ArtistsPage.vue'

const push = vi.fn()
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))
vi.mock('naive-ui', async () => {
  const actual: any = await vi.importActual('naive-ui')
  return { ...actual, useMessage: () => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn() }) }
})

const ITEM = {
  entry_key: 'artist:danbooru:1', source: 'danbooru', name: 'ebifurya', tag: 'ebifurya',
  thumb1_url: '/api/cf/asset?kind=artist&source=danbooru&key=1&which=1',
  thumb2_url: '/api/cf/asset?kind=artist&source=danbooru&key=1&which=2',
  favorite: false,
}

describe('ArtistsPage', () => {
  beforeEach(() => { vi.unstubAllGlobals(); push.mockClear() })

  function stubFetch(items: any[] = [ITEM]) {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url.includes('/api/cf/artists')) return { ok: true, json: async () => ({ items, total: items.length }) } as any
      if (url.includes('/api/cf/artist/favorite')) return { ok: true, json: async () => ({ favorite: true }) } as any
      return { ok: true, json: async () => ({ items: [], total: 0 }) } as any
    }))
  }

  it('渲染列表：卡片缩略图用 thumb1_url + 名称', async () => {
    stubFetch()
    const w = mount(ArtistsPage, { global: { stubs: { NImage: true } } })
    await flushPromises()
    expect(w.text()).toContain('ebifurya')
    expect(w.html()).toContain('which=1')
  })

  it('点击卡片跳转艺术家详情', async () => {
    stubFetch()
    const w = mount(ArtistsPage, { global: { stubs: { NImage: true } } })
    await flushPromises()
    const card = w.findComponent({ name: 'ImageCard' })
    ;(card.vm as any).open()
    expect(push).toHaveBeenCalledWith('/artists/danbooru/1')
  })

  it('收藏 toggle 调 /api/cf/artist/favorite', async () => {
    const calls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url.includes('/api/cf/artist/favorite')) calls.push(url)
      if (url.includes('/api/cf/artists')) return { ok: true, json: async () => ({ items: [ITEM], total: 1 }) } as any
      return { ok: true, json: async () => ({ favorite: true }) } as any
    }))
    const w = mount(ArtistsPage, { global: { stubs: { NImage: true } } })
    await flushPromises()
    const card = w.findComponent({ name: 'ImageCard' })
    ;(card.vm as any).$emit('toggle-favorite', ITEM)
    await flushPromises()
    expect(calls.some(u => u.includes('/api/cf/artist/favorite?source=danbooru&key=1'))).toBe(true)
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/__tests__/ArtistsPage.test.ts`
Expected: FAIL（组件不存在）

- [ ] **Step 3: 实现 `frontend/src/views/ArtistsPage.vue`**

```vue
<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { NCard, NSelect, NInput, NEmpty, NPagination, useMessage } from 'naive-ui'
import ImageCard from '../components/ImageCard.vue'
import { searchArtists, toggleArtistFavorite, parseEntryKey } from '../api/characterfinder'

const msg = useMessage(); const router = useRouter()
const SOURCE_OPTIONS = [
  { label: 'Danbooru 画师', value: 'danbooru' },
  { label: 'Anima 画师', value: 'anima' },
]
const source = ref('danbooru')
const query = ref('')
const page = ref(1); const size = ref(50)
const total = ref(0); const items = ref<any[]>([])
const loading = ref(false)

let timer: any = null
let lastReq = 0
async function load() {
  loading.value = true
  const myReq = ++lastReq
  try {
    const r = await searchArtists(query.value, source.value, page.value, size.value)
    if (myReq !== lastReq) return
    items.value = r.items; total.value = r.total
  } catch (e: any) { msg.error('加载失败：' + e.message) } finally { if (myReq === lastReq) loading.value = false }
}
onMounted(load)
function onQuery() { clearTimeout(timer); timer = setTimeout(() => { page.value = 1; load() }, 350) }
function onSource() { page.value = 1; load() }
function onPage(p: number) { page.value = p; load() }
onBeforeUnmount(() => clearTimeout(timer))

function cardTo(item: any) {
  const [, src, key] = parseEntryKey(item.entry_key)
  return `/artists/${src}/${encodeURIComponent(key)}`
}
function cardImg(item: any) { return item.thumb1_url }
function cardTags(item: any) { return item.tag ? String(item.tag).split(',').map((s: string) => s.trim()).filter(Boolean) : [] }
async function onToggleFav(item: any) {
  const [, src, key] = parseEntryKey(item.entry_key)
  try {
    const r = await toggleArtistFavorite(src, key)
    const t = items.value.find(i => i.entry_key === item.entry_key)
    if (t) t.favorite = r.favorite
  } catch (e: any) { msg.error('收藏失败：' + e.message) }
}
</script>

<template>
  <n-card class="filter-bar">
    <n-select v-model:value="source" :options="SOURCE_OPTIONS" size="small" style="width:160px" @update:value="onSource" />
    <n-input v-model:value="query" placeholder="搜索画师名 / tag" size="small" clearable style="width:240px" @update:value="onQuery" />
  </n-card>
  <n-empty v-if="!loading && items.length === 0" description="暂无画师" style="margin:40px 0" />
  <n-grid cols="2 600:3 900:5 1200:6" :x-gap="12" :y-gap="12">
    <n-gi v-for="item in items" :key="item.entry_key">
      <ImageCard :item="item" :to="cardTo(item)" :img-src="cardImg(item)" :title-text="item.name"
                 :tags-list="cardTags(item)" :favorite="!!item.favorite" @toggle-favorite="onToggleFav(item)" />
    </n-gi>
  </n-grid>
  <n-pagination v-if="total > size" :page="page" :item-count="total" :page-size="size"
                :page-slot="7" style="margin-top:16px;justify-content:center" @update:page="onPage" />
</template>

<style scoped>
.filter-bar { margin-bottom: 12px }
.filter-bar :deep(.n-card__content) { display: flex; gap: 8px; align-items: center; flex-wrap: wrap }
</style>
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npx vitest run src/__tests__/ArtistsPage.test.ts`
Expected: PASS（3 用例）

- [ ] **Step 5: 提交（8a）**

```bash
git add frontend/src/views/ArtistsPage.vue frontend/src/__tests__/ArtistsPage.test.ts
git commit -m "feat(cf): add ArtistsPage list (source/search + ImageCard reuse)"
```

#### Task 8b: ArtistDetailPage 详情页（双图）

- [ ] **Step 6: 写失败测试**

Create `frontend/src/__tests__/ArtistDetailPage.test.ts`:
```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ArtistDetailPage from '../views/ArtistDetailPage.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { source: 'danbooru', key: '1' } }),
  useRouter: () => ({ push: vi.fn() }),
}))
vi.mock('naive-ui', async () => {
  const actual: any = await vi.importActual('naive-ui')
  return { ...actual, useMessage: () => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn() }) }
})
vi.mock('../composables/useTagger', () => {
  const state = { selected: 'wd14', taggers: [{ key: 'wd14', label: 'WD14', downloaded: true }], downloading: null }
  return { useTagger: () => ({ state, setSelected: vi.fn(), refresh: vi.fn(async () => {}), isDownloaded: () => true, download: vi.fn(async () => {}) }) }
})

const DETAIL = {
  entry_key: 'artist:danbooru:1', source: 'danbooru', name: 'ebifurya', tag: 'ebifurya',
  thumb1_url: '/api/cf/asset?kind=artist&source=danbooru&key=1&which=1',
  thumb2_url: '/api/cf/asset?kind=artist&source=danbooru&key=1&which=2',
  favorite: false, locked_tags: ['ebifurya'],
  categories: { head: { tags: ['rough sketch'], phrase: 'rough sketch', user_edited: false } },
  extras: { tags: [], phrase: '', user_edited: false },
  custom_tags: [], model: 'wd14', gen_threshold: 0.35, char_threshold: 0.9, image_override: null,
}

describe('ArtistDetailPage', () => {
  beforeEach(() => vi.unstubAllGlobals())
  function stubFetch(handler: (url: string, opts?: any) => any) {
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts?: any) => ({ ok: true, json: async () => handler(url, opts) } as any)))
  }

  it('加载详情：渲染双图 + 锁定画师 tag + 分类标签', async () => {
    stubFetch((url) => { if (url.includes('/api/cf/artist?')) return DETAIL; return {} })
    const w = mount(ArtistDetailPage, { global: { stubs: { NImage: true, NUpload: true } } })
    await flushPromises()
    const html = w.html()
    expect(html).toContain('which=1')
    expect(html).toContain('which=2')
    expect(w.findAll('.locked-tag').map(t => t.text())).toContain('🔒 ebifurya')
    expect(w.text()).toContain('rough sketch')
  })

  it('save 的 PUT body 含 categories/extras/custom_tags，不含 locked_tags', async () => {
    const seen: any[] = []
    stubFetch((url, opts) => {
      if (url.includes('/api/cf/artist?') && opts && opts.method === 'PUT') seen.push(opts.body)
      if (url.includes('/api/cf/artist?')) return DETAIL
      return {}
    })
    const w = mount(ArtistDetailPage, { global: { stubs: { NImage: true, NUpload: true } } })
    await flushPromises()
    await (w.vm as any).save()
    await flushPromises()
    expect(seen.length).toBe(1)
    const body = JSON.parse(seen[0])
    expect(body.categories).toBeTruthy()
    expect(body.locked_tags).toBeUndefined()
  })

  it('收藏 toggle 调 /api/cf/artist/favorite', async () => {
    const urls: string[] = []
    stubFetch((url) => {
      if (url.includes('/api/cf/artist/favorite')) { urls.push(url); return { favorite: true } }
      if (url.includes('/api/cf/artist?')) return DETAIL
      return {}
    })
    const w = mount(ArtistDetailPage, { global: { stubs: { NImage: true, NUpload: true } } })
    await flushPromises()
    await (w.vm as any).toggleFav()
    await flushPromises()
    expect(urls.some(u => u.includes('/api/cf/artist/favorite?source=danbooru&key=1'))).toBe(true)
  })
})
```

- [ ] **Step 7: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/__tests__/ArtistDetailPage.test.ts`
Expected: FAIL（组件不存在）

- [ ] **Step 8: 实现 `frontend/src/views/ArtistDetailPage.vue`**

```vue
<script setup lang="ts">
import { ref, computed, watch, onMounted, h } from 'vue'
import { useRoute } from 'vue-router'
import {
  NSpace, NButton, NRadioGroup, NRadioButton, NImage, NCard,
  NInputNumber, NInput, NDynamicTags, NTag, NUpload, NSelect, useMessage,
} from 'naive-ui'
import TagEditor from '../components/TagEditor.vue'
import {
  getArtist, tagArtist, reclassifyArtist, saveArtist,
  uploadArtistImage, toggleArtistFavorite, type CfDetail,
} from '../api/characterfinder'
import { useTagger } from '../composables/useTagger'
import { buildPromptWithLocked } from '../detail-utils'
import { IconPlus } from '../components/icons'

const tagger = useTagger()
const route = useRoute(); const msg = useMessage()
const source = computed(() => route.params.source as string)
const key = computed(() => route.params.key as string)

const KEY_TITLES: [string, string, string][] = [
  ['head', '画风/笔触', '#4CAF50'], ['clothing', '服装', '#2196F3'],
  ['view', '视角构图', '#9C27B0'], ['action', '动作', '#FF9800'],
  ['scene', '场景', '#795548'], ['quality', '质量词（预设）', '#607D8B'],
]

const detail = ref<CfDetail | null>(null)
const mode = ref<'tags' | 'phrase'>('tags')
const dirty = ref(false)
const genTh = ref(0.35); const charTh = ref(0.9)
const localModel = ref('')
const handEdited = ref<Set<string>>(new Set())
const imgVersion = ref(0)

const taggerOptions = computed(() => tagger.state.taggers.map(t => ({ label: t.label, value: t.key, downloaded: t.downloaded })))
function renderTaggerLabel(option: any) {
  return h('span', { style: 'display:inline-flex;align-items:center;gap:6px' }, [
    option.label as any,
    option.downloaded ? h(NTag, { type: 'success', size: 'small', bordered: false }, { default: () => '已下载' })
                       : h(NTag, { size: 'small', bordered: false }, { default: () => '未下载' }),
  ])
}
const modelDownloaded = computed(() => tagger.isDownloaded(localModel.value))
onMounted(() => { tagger.refresh() })
async function doDownload() {
  try { await tagger.download(localModel.value); msg.success('下载完成') }
  catch (e: any) { msg.error('下载失败：' + e.message) }
}
let modelChangeFromLoad = false
watch(localModel, (m) => {
  if (modelChangeFromLoad) { modelChangeFromLoad = false; return }
  if (m === 'cl_tagger_v2') { genTh.value = 0.55; charTh.value = 0.55 }
})

function fromDetail(d: CfDetail) {
  detail.value = d; dirty.value = false; handEdited.value = new Set()
  if (d.model === 'cl_tagger_v2') { genTh.value = 0.55; charTh.value = 0.55 }
  else { genTh.value = d.gen_threshold; charTh.value = d.char_threshold }
  modelChangeFromLoad = true; localModel.value = d.model
}
async function load() {
  const s = source.value, k = key.value
  try {
    const d = await getArtist(s, k)
    if (s !== source.value || k !== key.value) return
    fromDetail(d)
  } catch (e: any) { msg.error('加载失败：' + e.message) }
}
watch([source, key], load, { immediate: true })

function setCat(k: string, val: any) { detail.value!.categories[k] = val; dirty.value = true; if (val.user_edited) handEdited.value.add(k) }
function setExtras(val: any) { detail.value!.extras = val; dirty.value = true }
function onCustomTags(v: string[]) { detail.value!.custom_tags = v; dirty.value = true }
function applyPhrase(k: string, tags: string[]) {
  const next = { tags, phrase: tags.join(', '), user_edited: true }
  if (k === 'extras') setExtras(next); else setCat(k, next)
}
async function save() {
  if (!detail.value) return
  try {
    const d = await saveArtist(source.value, key.value, {
      categories: detail.value.categories, extras: detail.value.extras, custom_tags: detail.value.custom_tags,
    })
    fromDetail(d); msg.success('已保存')
  } catch (e: any) { msg.error('保存失败：' + e.message) }
}
async function reTag() {
  try {
    const d = await tagArtist(source.value, key.value, genTh.value, charTh.value, localModel.value)
    fromDetail(d); msg.success('反推完成')
  } catch (e: any) { msg.error('反推失败：' + e.message) }
}
async function reClassify() {
  const keep: Record<string, string[]> = {}
  handEdited.value.forEach(k => { keep[k] = detail.value!.categories[k].tags })
  try {
    const d = await reclassifyArtist(source.value, key.value, keep)
    fromDetail(d); msg.success('重分类完成（跳过手改类）')
  } catch (e: any) { msg.error('重分类失败：' + e.message) }
}
async function uploadImage(file: File) {
  try {
    const r = await uploadArtistImage(source.value, key.value, file)
    detail.value!.image_override = r.image_override; imgVersion.value++; msg.success('图片已替换')
  } catch (e: any) { msg.error('上传失败：' + e.message) }
}
function onUploadReq({ file }: any) { const f = (file as any)?.file as File | undefined; if (f) uploadImage(f) }
async function toggleFav() {
  try {
    const r = await toggleArtistFavorite(source.value, key.value)
    detail.value!.favorite = r.favorite
  } catch (e: any) { msg.error('收藏失败：' + e.message) }
}
const fullPrompt = computed(() => detail.value ? buildPromptWithLocked(detail.value, detail.value.locked_tags) : '')
async function copyPrompt() {
  if (!fullPrompt.value) { msg.warning('暂无提示词'); return }
  try { await navigator.clipboard.writeText(fullPrompt.value); msg.success('已复制完整 prompt') }
  catch { msg.error('复制失败') }
}
const v = () => imgVersion.value ? `&_v=${imgVersion.value}` : ''
const img1Src = computed(() => detail.value ? detail.value.thumb1_url + v() : '')
const img2Src = computed(() => detail.value ? detail.value.thumb2_url + v() : '')
</script>

<template>
  <div v-if="detail" style="display:grid;grid-template-columns:minmax(280px,1fr) minmax(0,2fr);gap:16px">
    <div>
      <n-card>
        <div class="img-wrap">
          <!-- 双图：danbooru 画师两张参考图 -->
          <div class="dual-img">
            <n-image v-if="img1Src" :src="img1Src" :preview-src="img1Src" object-fit="contain" style="max-height:300px;width:100%;display:block" />
            <n-image v-if="img2Src" :src="img2Src" :preview-src="img2Src" object-fit="contain" style="max-height:300px;width:100%;display:block" />
          </div>
          <div v-if="!img1Src && !img2Src" class="no-img">暂无图片</div>
        </div>
        <div style="font-size:12px;margin-top:8px">
          <div style="margin-bottom:4px">
            <span style="font-weight:600">{{ detail.name }}</span>
            <span v-if="detail.tag && detail.tag !== detail.name" style="color:var(--n-text-color-3,#888);margin-left:8px">{{ detail.tag }}</span>
          </div>
          <div>{{ detail.source }}</div>
          <div style="margin-top:6px">
            <div style="font-size:13px;margin-bottom:4px">反推模型</div>
            <n-select :value="localModel" :options="taggerOptions" :render-label="renderTaggerLabel"
                      @update:value="(val: string) => localModel = val" size="small" style="max-width:260px" />
            <div v-if="!modelDownloaded" style="margin-top:4px;display:flex;align-items:center;gap:6px">
              <span style="font-size:12px;color:#d03050">{{ tagger.state.taggers.find(t=>t.key===localModel)?.label || localModel }} 未下载</span>
              <n-button size="tiny" :loading="tagger.state.downloading===localModel" @click="doDownload">下载</n-button>
            </div>
          </div>
          <div>通用 <n-input-number v-model:value="genTh" :step="0.05" :min="0" :max="1" size="small" style="width:96px" /></div>
          <div style="margin-top:6px">
            <div style="color:var(--cat-input-color,#888);margin-bottom:2px">自定义标签</div>
            <n-dynamic-tags :value="detail.custom_tags || []" size="small" @update:value="onCustomTags" />
          </div>
        </div>
        <n-space vertical style="margin-top:8px">
          <n-upload :show-file-list="false" :max="1" accept="image/*" :custom-request="onUploadReq">
            <n-button size="small"><IconPlus/> 替换图片</n-button>
          </n-upload>
          <n-button size="small" @click="reTag">重新反推</n-button>
          <n-button size="small" @click="reClassify">重分类</n-button>
          <n-button size="small" @click="copyPrompt">复制完整 prompt</n-button>
          <n-button size="small" :type="detail.favorite ? 'warning' : 'default'" @click="toggleFav">
            {{ detail.favorite ? '★ 已收藏' : '☆ 收藏' }}
          </n-button>
        </n-space>
      </n-card>
    </div>
    <div>
      <div v-if="detail.locked_tags && detail.locked_tags.length" class="locked-box">
        <span class="locked-title">🔒 锁定画师 tag（权威，不可编辑）</span>
        <div class="locked-tags">
          <n-tag v-for="t in detail.locked_tags" :key="'lock-' + t" class="locked-tag" size="small" round :bordered="false" type="warning">{{ '🔒 ' + t }}</n-tag>
        </div>
      </div>
      <n-space align="center" style="margin-bottom:10px">
        <n-radio-group v-model:value="mode" size="small">
          <n-radio-button value="tags">标签</n-radio-button>
          <n-radio-button value="phrase">短句</n-radio-button>
        </n-radio-group>
        <n-button size="small" type="primary" :disabled="!dirty" @click="save">保存</n-button>
      </n-space>
      <TagEditor v-for="[k, title, color] in KEY_TITLES" :key="k" :title="title" :color="color"
                 :mode="mode" :category-key="k"
                 :model-value="detail.categories[k] || { tags: [], phrase: '', user_edited: false }"
                 @update:modelValue="(val) => setCat(k, val)" @apply-phrase="(t) => applyPhrase(k, t)" />
      <TagEditor title="未归类 extras（拖到各类为复制，不会移除原标签）" color="#9E9E9E" :mode="mode"
                 category-key="extras" :model-value="detail.extras"
                 @update:modelValue="setExtras" @apply-phrase="(t) => applyPhrase('extras', t)" />
    </div>
  </div>
</template>

<style scoped>
:deep(.n-image) { display: block; width: 100% }
:deep(.n-image img) { max-width: 100%; max-height: 300px; width: auto; height: auto; object-fit: contain; display: block; margin: 0 auto }
.img-wrap { border-radius: 10px; padding: 8px; display: flex; align-items: center; justify-content: center }
.dual-img { display: flex; flex-direction: column; gap: 8px; width: 100% }
.no-img { height: 200px; display: flex; align-items: center; justify-content: center; font-size: 13px }
.locked-box { border: 1px dashed #d4a017; border-radius: 8px; padding: 8px 10px; margin-bottom: 12px; background: var(--cat-panel-bg, #fafafa) }
.locked-title { font-size: 12px; font-weight: 600; color: #b8860b; display: block; margin-bottom: 6px }
.locked-tags { display: flex; flex-wrap: wrap; gap: 4px }
</style>
```

- [ ] **Step 9: 跑测试确认通过**

Run: `cd frontend && npx vitest run src/__tests__/ArtistDetailPage.test.ts`
Expected: PASS（3 用例）

- [ ] **Step 10: 提交（8b）**

```bash
git add frontend/src/views/ArtistDetailPage.vue frontend/src/__tests__/ArtistDetailPage.test.ts
git commit -m "feat(cf): add ArtistDetailPage (dual images + locked artist tag)"
```

---

### Task 5b: router + App 接线（菜单与路由注册）

> **执行顺序**：本 task 必须在 Task 6/7/8（4 个页面组件已创建）之后执行——否则 `router.ts` import 尚不存在的组件会导致 `npm run build` 失败。

**Files:**
- Modify: `frontend/src/router.ts`（顶部 import 4 组件 + routes 追加 4 路由）
- Modify: `frontend/src/App.vue`（import 2 icon + ITEMS 追加 2 菜单项）
- Test: `frontend/src/__tests__/router.test.ts`（新建）

**Interfaces:**
- Consumes: Task 5a `IconCharacter`/`IconArtist`；Task 6/7/8 `CharactersPage`/`CharacterDetailPage`/`ArtistsPage`/`ArtistDetailPage`
- Produces: 4 条前端路由 + 侧栏 2 个菜单入口；activeKey 经 `path.startsWith('/characters')`/`/artists` 自动匹配（无需改 currentTitle 特判，沿用现有 longest-prefix 逻辑）

- [ ] **Step 1: 写失败测试**

Create `frontend/src/__tests__/router.test.ts`:
```typescript
import { describe, it, expect } from 'vitest'
import router from '../router'

describe('router routes', () => {
  it('注册角色与艺术家路由', () => {
    const paths = router.getRoutes().map(r => r.path)
    expect(paths).toContain('/characters')
    expect(paths).toContain('/characters/:source/:key')
    expect(paths).toContain('/artists')
    expect(paths).toContain('/artists/:source/:key')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/__tests__/router.test.ts`
Expected: FAIL（4 路由不存在）

- [ ] **Step 3: 修改 `frontend/src/router.ts`**

在文件顶部 import 区追加（与现有 view import 同风格；若现有为懒加载 `() => import(...)`，则保持一致改用懒加载）：
```typescript
import CharactersPage from './views/CharactersPage.vue'
import CharacterDetailPage from './views/CharacterDetailPage.vue'
import ArtistsPage from './views/ArtistsPage.vue'
import ArtistDetailPage from './views/ArtistDetailPage.vue'
```

在 `routes` 数组中追加 4 个路由对象（建议放在 `/collections` 之前，保持 cf 模块聚集）：
```typescript
{ path: '/characters', component: CharactersPage },
{ path: '/characters/:source/:key', component: CharacterDetailPage, props: true },
{ path: '/artists', component: ArtistsPage },
{ path: '/artists/:source/:key', component: ArtistDetailPage, props: true },
```

> `:source/:key` 两段路径天然规避 anima key 含空格/逗号的路径问题（详情页内部已 `encodeURIComponent` 跳转；vue-router 自动 decode params）。

- [ ] **Step 4: 修改 `frontend/src/App.vue`**

在顶部 icon import 追加（Task 5a 已创建这两个 icon）：
```typescript
import { IconCharacter, IconArtist } from './components/icons'
```

在 `ITEMS` 数组中追加 2 项（插入位置：建议在「图库」之后、「随机」之前，或紧跟现有项末尾；`key` 必须与 router path 前缀一致）：
```typescript
{ label: '角色图鉴', key: '/characters', icon: IconCharacter },
{ label: '艺术家', key: '/artists', icon: IconArtist },
```

> activeKey 现有逻辑 `ITEMS.map(i=>i.key).filter(k=>path.startsWith(k)).sort(by length desc)[0]` 会把 `/characters/danbooru/1` 正确归到 `/characters`，标题显示「角色图鉴」——与 PromptboxDetailPage 复用「提示词收藏」标题同一风格，无需特判。

- [ ] **Step 5: 跑测试确认通过**

Run:
```bash
cd frontend
npx vitest run src/__tests__/router.test.ts
npm run build
```
Expected: router.test PASS（4 路由注册）；`npm run build`（vue-tsc 类型检查 + vite 构建）成功，证明 4 个新页面组件均能被 router 正确 import 与编译。

- [ ] **Step 6: 全量回归**

Run: `cd frontend && npx vitest run`
Expected: 全绿（含 Task 1-8 新增测试 + 21 个原有测试）

- [ ] **Step 7: 提交**

```bash
git add frontend/src/router.ts frontend/src/App.vue frontend/src/__tests__/router.test.ts
git commit -m "feat(cf): wire characters/artists routes and menu entries"
```

---

## Self-Review

### 1. Spec 覆盖（对照设计 §5 前端 + §9 P2 范围）

| 设计要求 | 实现任务 | 状态 |
|---|---|---|
| §5.1 路由 `/characters` + `/artists`（含详情子路由） | Task 5b（4 条路由） | ✅ |
| §5.2 API 客户端 `characterfinder.ts`（扁平 fetch） | Task 1 | ✅ |
| §5.3 列表页复用 ImageCard | Task 6（角色）+ Task 8a（艺术家） | ✅ |
| §5.4 详情页复用 DetailPage 双栏布局 + 🔒 锁定标签区 | Task 7（角色）+ Task 8b（艺术家，双图） | ✅ |
| §5.5 组件增强：ImageCard 通用化 / TagEditor lockedTags | Task 3 / Task 4 | ✅ |
| §8 无新增 npm 依赖 | 全 task 用现有 vue/naive-ui/vitest 栈 | ✅ |
| §10 锁定标签不可绕过 | Task 2 `buildPromptWithLocked` + Task 1 `CfSaveBody` 无 locked 字段 + Task 7/8b 独立锁区只读 | ✅ |
| §9 P2 = API + 列表 + 详情 + 组件增强 | Task 1-8 全覆盖 | ✅ |

**P2 不含**（留 P3/P4）：RandomPage 来源切换、收藏夹/最近查看 UI、`/api/cf/favorites` 页面、cf 下载脚本（cf_download_covers/cf_import_animadex/cf_sync_from_sdcf）。后端 favorites/recent/random 端点已由 P1（Task 11）提供，P3 前端接入即可。

### 2. Placeholder 扫描

- 无 TBD/TODO/"implement later"/"similar to Task N"。
- Task 5b Step 3/4 为 Modify 指令，附精确代码块（import 行 + routes 对象 + ITEMS 项），非省略。
- 所有"新增"组件（Task 1/3/4/6/7/8）均贴完整 `.vue`/`.ts` 全文。

### 3. 类型一致性

跨 task 符号核对一致：
- `parseEntryKey`/`cfAssetUrl`（Task 1）← CharactersPage/ArtistsPage `cardTo` 使用 ✓
- `buildPromptWithLocked(meta, lockedTags=[])`（Task 2）← CharacterDetailPage/ArtistDetailPage `fullPrompt` 使用 ✓
- ImageCard props `to/imgSrc/titleText/tagsList/copyText/downloadSrc/downloadName/favorite` + emit `toggle-favorite`（Task 3）← Task 6/8a 传参一致 ✓
- `CfDetail`/`CfSaveBody`/`CfListItem`/`CfCategoryView`（Task 1）← 详情页/列表页类型一致 ✓
- cf API 函数名 `searchCharacters`/`getCharacter`/`tagCharacter`/... 与 `searchArtists`/`getArtist`/...（Task 1）← 详情页/列表页调用一致 ✓
- `IconCharacter`/`IconArtist`（Task 5a）← App.vue ITEMS（Task 5b）使用 ✓

### 4. 已知项（非阻塞）

- **`listArtistSeries`（Task 1）无消费者**：艺术家无 series 概念，ArtistsPage 不调用该函数。执行 Task 1 时可安全省略（YAGNI）；若已实现，未引用导出无害（不影响功能），可保留或删除。已在 Task 8 开头 note 标注。
- **详情页锁定标签用独立锁区而非 TagEditor.lockedTags**：`locked_tags` 跨所有类（trigger+core_tags / 画师 tag），不属于单个分类 TagEditor，故用右栏顶部独立 `.locked-tag` 区呈现。TagEditor.lockedTags（Task 4）为设计 §5.5 mandated 的组件能力，保留供未来分类级锁定。
- **anima key 含空格/逗号/括号**：前端路由 `:source/:key` 中 `key` 经 `encodeURIComponent`（列表页 cardTo）+ vue-router 自动 decode params 处理；后端 API 仍用 query `?source=&key=`（cf 客户端构造）。anima 名不含 `/`，path 段安全。
- **后端合约由 P1 pytest 覆盖**（231 passed）：前端测试只验封装（URL 构造/请求体形状）与组件渲染/交互，不重复测后端。
- **随机性（M13）**：P1 random 端点首版用 `search("")` 取前 N，非真随机；P2 不接入 random UI（留 P3）。

### 验证策略

- 单 task：`cd frontend && npx vitest run src/__tests__/<file>.test.ts`
- 全量回归：`cd frontend && npx vitest run`（21 原有 + P2 新增）
- 类型/构建：`cd frontend && npm run build`（vue-tsc + vite）
- 后端不受 P2 影响（P1 已合并 master，231 passed）

---

## Execution Handoff

计划已完成并保存至 `docs/superpowers/plans/2026-06-21-characterfinder-frontend-p2.md`。

**两种执行方式：**

1. **Subagent-Driven（推荐）** — 每个 task 派发独立 implementer 子代理 + task reviewer 双审，task 间快速迭代，主控保留协调上下文。适用于本计划：8 个 task 边界清晰、依赖线性（1→2→3/4→5a→6→7→8→5b）、每个 task 自带 TDD 测试可独立验证。
2. **Inline Execution** — 在当前会话按 executing-plans 批量执行，带 checkpoint 审查。

如选 Subagent-Driven，需用 `superpowers:subagent-driven-development` 技能：为每个 task 运行 `task-brief` 提取需求文件，dispatch implementer（Task 1/3/4/6 等含完整代码的转录型任务用 cheap model；Task 7/8b 多文件集成用 standard model），完成后 `review-package` + task reviewer 双审，全 branch 完成后派发 final code-reviewer，最后用 `finishing-a-development-branch` 收尾。
