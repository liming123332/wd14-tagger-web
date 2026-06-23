# 收藏列表分页 + 随机页「提示词收藏」来源 — 设计规格

日期：2026-06-23

## 背景

- `/collections`（[CollectionListPage.vue](../../../frontend/src/views/CollectionListPage.vue)）是**提示词收藏列表**：`listPromptbox()` 全量加载所有 `PromptboxItem` → 前端 `filtered`（标题/raw_prompt 子串过滤）→ `n-grid` 全量渲染，**无分页**。收藏增多后单页渲染过重且难以翻阅。
- 随机抽取页（[RandomPage.vue](../../../frontend/src/views/RandomPage.vue)）来源只有 图库 / 角色图鉴 / 艺术家，**无法从提示词收藏里随机抽取**。

## 目标

1. `/collections` 列表加**页码分页**。
2. RandomPage 新增**「提示词收藏」来源**，可随机抽收藏卡片。

## 非目标（YAGNI）

- 后端分页（`listPromptbox` 加 page/size）：收藏全量加载供前端搜索，后端分页需重建搜索逻辑，无收益。
- 抽公共 `PromptboxCard.vue` 组件：列表页卡片含「复制/删除」按钮与分类计数，随机页只要浏览，差异大，内联精简卡片即可。
- 收藏不足时凑数重复：只取现有的，不重复。

## 现状（关键事实）

- `listPromptbox(): Promise<PromptboxItem[]>` 返回全部收藏；`promptboxImageUrl(id, name)` 拼封面 URL。
- `PromptboxItem`：`{ id, title, raw_prompt, categories, extras, image_names[], ... }`（多图提示词卡片）。
- RandomPage 现状：`source: 'gallery'|'characters'|'artists'`、`cfSource: 'anima'|'danbooru'`；`shuffle()` 按 source 调 `randomImages` 或 `randomCf`；渲染 `ImageCard`（gallery 用默认 props，cf 带 `to/img-src/title-text/tags-list`）。**已有竞争条件防御**：`onSource` 切源先 `items.value = []` 再 shuffle，`cardTo` 防御 `entry_key` 为空。
- CollectionListPage 现状：`items`（全量）→ `filtered`（computed 搜索）→ `n-grid` 渲染 `filtered`。

## 设计

### 需求 1：`/collections` 页码分页（纯前端，无后端改动）

[CollectionListPage.vue](../../../frontend/src/views/CollectionListPage.vue)：

- 新增 `const page = ref(1)`、`const PAGE_SIZE = 30`。
- 新增 computed：
  ```ts
  const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / PAGE_SIZE)))
  const paged = computed(() => {
    const start = (page.value - 1) * PAGE_SIZE
    return filtered.value.slice(start, start + PAGE_SIZE)
  })
  ```
- 网格 `v-for` 由 `filtered` 改为 `paged`。
- 页码夹紧（防越界，覆盖删除/搜索导致条目减少）：
  ```ts
  watch(totalPages, (tp) => { if (page.value > tp) page.value = tp })
  ```
- 搜索框 `@update:value` 时额外 `page = 1`（搜索后回到第一页，直觉行为）。
- 底部 `NPagination`（仅在超过一页时渲染）：
  ```html
  <n-pagination v-if="filtered.length > PAGE_SIZE" :page="page"
               :item-count="filtered.length" :page-size="PAGE_SIZE"
               @update:page="(p: number) => page = p" style="margin-top:16px;justify-content:center" />
  ```
- `NPagination` 需在 `import { ... } from 'naive-ui'` 中加入。

### 需求 2：RandomPage 新增「提示词收藏」来源

[RandomPage.vue](../../../frontend/src/views/RandomPage.vue)：

- `source` 类型扩展为 `'gallery' | 'characters' | 'artists' | 'promptbox'`。
- `SOURCE_OPTIONS` 追加 `{ label: '提示词收藏', value: 'promptbox' }`。
- cfSource 下拉的渲染条件由 `source !== 'gallery'` 改为 `source !== 'gallery' && source !== 'promptbox'`（收藏不分 anima/danbooru）。
- 新增前端抽样工具（不足取全部、不重复）：
  ```ts
  function pickRandom<T>(arr: T[], n: number): T[] {
    const a = [...arr]
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1))
      ;[a[i], a[j]] = [a[j], a[i]]
    }
    return a.slice(0, Math.min(n, a.length))
  }
  ```
- `shuffle()` 增加分支：
  ```ts
  if (source.value === 'gallery') {
    items.value = (await randomImages(size)).items
  } else if (source.value === 'promptbox') {
    items.value = pickRandom(await listPromptbox(), size)
  } else {
    const type = source.value === 'characters' ? 'characters' : 'artists'
    items.value = (await randomCf(type, cfSource.value, size)).items
  }
  ```
- `import` 增加 `listPromptbox, promptboxImageUrl` from `../api/client`，并 `import { useRouter } from 'vue-router'` + `const router = useRouter()`。
- 渲染分支（`source === 'promptbox'` 用精简收藏卡片，点击跳详情；其余保持现有 ImageCard 分支）：
  ```html
  <n-grid-item v-for="it in items" :key="(it.entry_key as string) ?? (it.id as string)">
    <n-card v-if="source === 'promptbox'" size="small" hoverable
            @click="router.push(`/collections/${it.id}`)" style="cursor:pointer">
      <div class="title">{{ it.title || '(未命名)' }}</div>
      <n-image v-if="it.image_names?.length" width="100%" object-fit="cover" preview-disabled
               :src="promptboxImageUrl(it.id, it.image_names[0])" />
      <div class="prompt">{{ it.raw_prompt || '(无提示词)' }}</div>
    </n-card>
    <ImageCard v-else-if="source === 'gallery'" :item="it" />
    <ImageCard v-else :item="it" :to="cardTo(it)" ... />
  </n-grid-item>
  ```
  （`prompt` 摘要样式复用 CollectionListPage 的 `-webkit-line-clamp:2` 截断。）
- 空态：`n-empty` 的 `description` 三元里追加 promptbox 文案（`source === 'promptbox' ? '还没有提示词收藏，去提示词收藏页创建' : ...`）。

### 复用现有竞争条件防御

`onSource` 切源已 `items.value = []` 再 shuffle；新来源 `promptbox` 自动受益（切源中间帧 items 为空，不渲染卡片）。promptbox 卡片不调 `parseEntryKey`，无 `split(undefined)` 风险。

## 测试

### 前端 vitest

[CollectionListPage.test.ts](../../../frontend/src/__tests__/CollectionListPage.test.ts)（已存在）增补：
- **切片**：mock `listPromptbox` 返回 75 条 → `page=1` 渲染 30、`page=2` 渲染 30、`page=3` 渲染 15。
- **夹紧**：`page=3` 时删除/过滤使总数降到 40（总页数 2）→ `page` 自动夹紧到 2。
- **搜索重置**：搜索框输入后 `page` 回到 1。
- **分页器显隐**：条数 ≤ PAGE_SIZE 时不渲染 `NPagination`。

[RandomPage.test.ts](../../../frontend/src/__tests__/RandomPage.test.ts)（已存在）增补：
- **来源分发**：切到 `promptbox` → 调 `listPromptbox`，不调 `randomImages` / `randomCf`。
- **切源不崩**：复用现有竞态测试模式（切到 `promptbox` 中间帧不抛）。
- **抽样数量**：mock 返回 5 条、size=24 → 渲染 5 条（不足不重复）。

### 后端

零改动，不新增后端测试。

## 整合包同步

- 前端 `npm run build` → `frontend/dist`。
- dist 同步到两处整合包：
  - `i:\trae\wd14\WD14-Tagger-Web-Portable\wd14-tagger-web\frontend\dist`
  - `I:\WD14-Tagger-Web-Portable\wd14-tagger-web\frontend\dist`
- 后端无改动，不涉及后端同步。

## 风险与权衡

- **卡片视觉不一致**：promptbox 卡片与 ImageCard 样式不同。可接受——数据结构不同，来源切换语义清晰，且 promptbox 卡片复用 CollectionListPage 视觉语言。
- **前端随机抽样**：收藏全量已在内存，前端 Fisher-Yates 抽样足够；无需后端 RANDOM（与图库后端 `ORDER BY RANDOM()` 不同，因收藏量级小且需前端搜索）。
- **空收藏**：promptbox 来源走 `n-empty`，提示去提示词收藏页创建。
