# Character Finder P3 前端接入 设计

> **目标**：接入 P1 Task 11 已就绪的后端 `favorites` / `recent` / `random` 端点，前端提供 RandomPage 源切换（图库/角色/艺术家）、cf 收藏夹独立页、列表页最近查看区。纯前端增量，后端不动。

## 上下文

- **P1 后端**（已合并 master，231 passed）：Task 11 提供 3 个只读端点。
- **P2 前端**（已合并 master，160 passed）：cf API 客户端、CharactersPage/ArtistsPage 列表、CharacterDetailPage/ArtistDetailPage 详情、ImageCard 通用化、TagEditor lockedTags、icons、router/App 接线。锁定语义三重保险已落地。
- **本阶段（P3）**：补齐「浏览随机 cf 项」「查看收藏」「回到最近看过的」三条入口，全部消费 P1 已就绪端点。

## 后端契约（P1 Task 11 已就绪，本阶段不改）

所有端点返回 `{ items: CfListItem[] }`，item 形状与列表页 `search` 一致（角色含 `entry_key/source/name/series/core_tags/favorite`，艺术家含 `entry_key/source/name/tag/thumb1_url/thumb2_url/favorite`）。

| 端点 | 参数 | 用途 |
|---|---|---|
| `GET /api/cf/favorites` | `kind=char\|artist` | 收藏列表（entry_key 前缀过滤） |
| `GET /api/cf/recent` | `kind=char\|artist&limit=` | 最近查看（LIFO，上限 100） |
| `GET /api/cf/random` | `type=characters\|artists&source=danbooru\|anima&size=` | 随机 cf 项 |

## 架构

纯前端增量，4 处改动 + 1 个新视图：

1. **cf API 扩展**：`characterfinder.ts` 补 3 个 async 函数。
2. **RandomPage**：加源切换，复用现有页（图库随机保留，新增角色/艺术家随机）。
3. **CfFavoritesPage**（新视图）：cf 收藏夹独立页，角色/艺术家 tab。
4. **列表页最近查看区**：CharactersPage / ArtistsPage 顶部加横向滚动区。
5. **router + App + icon**：注册 `/cf/favorites` 路由 + 菜单项 + IconBookmark。

复用 P2 成果：ImageCard 通用化 props、parseEntryKey（对象解构）、cfAssetUrl、列表页 filter-bar/n-grid 视觉、详情页跳转路径。

## 组件设计

### 1. cf API 扩展（`frontend/src/api/characterfinder.ts`）

补 3 个 async 函数，仿现有 `searchCharacters` 风格（`const base=''` + 原生 fetch + URLSearchParams 编 query + 返回 `.json()`）：

```ts
export async function listCfFavorites(kind: 'char' | 'artist'): Promise<{ items: CfListItem[] }>
export async function listCfRecent(kind: 'char' | 'artist', limit = 50): Promise<{ items: CfListItem[] }>
export async function randomCf(type: 'characters' | 'artists', source: string, size = 24): Promise<{ items: CfListItem[] }>
```

### 2. RandomPage 源切换（`frontend/src/views/RandomPage.vue`）

- **state**：`source: 'gallery' | 'characters' | 'artists'`；当选 characters/artists 时另持 `cfSource: 'danbooru' | 'anima'`。
- **顶部控件**：源下拉（图库/角色图鉴/艺术家）+ 条件渲染的 cfSource 下拉（仅角色/艺术家时显示）。
- **shuffle()**：按 source 分发——`gallery`→`randomImages(size)`（现有 client.ts）；`characters`→`randomCf('characters', cfSource, size)`；`artists`→`randomCf('artists', cfSource, size)`。切源时自动重抽。
- **卡片**：图库用 `<ImageCard :item="it" />`（默认）；角色/艺术家用 `<ImageCard :item="it" :to :img-src :title-text :tags-list :favorite @toggle-favorite>`（to/imgSrc 等复用列表页 cardTo/cardImg 计算，角色跳 `/characters/:source/:key`、艺术家跳 `/artists/:source/:key`）。
- 保留现有「再抽一页」按钮 + n-empty + n-grid cols。

### 3. CfFavoritesPage 收藏夹页（新视图 `frontend/src/views/CfFavoritesPage.vue`，路由 `/cf/favorites`）

- **state**：`kind: 'char' | 'artist'`（tab）；`items`；`keyword`（前端子串搜索）。
- **顶部**：tab 切角色/艺术家 + 搜索框（仿 CollectionListPage filter-bar）。
- **加载**：`listCfFavorites(kind)`，kind 切换重新加载。
- **网格**：n-grid + ImageCard，to 跳对应详情（角色 `/characters/:source/:key`、艺术家 `/artists/:source/:key`）。
- **收藏 toggle 乐观移除**：点掉收藏后从 `items` filter 移除（不再属于收藏列表），无需整页重载。
- **前端搜索**：keyword 子串过滤 name/tag（cf 收藏量级小，无需后端分页）。
- 仿 CollectionListPage 视觉（filter-bar + n-grid cols + n-empty）。

### 4. 列表页最近查看区（改 CharactersPage / ArtistsPage）

- 在 filter-bar **之前**加「最近查看」横向滚动区（仅当 recent 非空时渲染）。
- `onMounted` 调 `listCfRecent(kind, 10)`（CharactersPage 用 `'char'`，ArtistsPage 用 `'artist'`）。
- 横向滚动小卡片：复用 ImageCard（固定窄宽，如每张 ~140px），点击跳详情。
- 无最近查看时整区 `v-if` 隐藏（不显示空态）。

### 5. router + App + icon

- **icons.ts**：新增 `IconBookmark`（现有 `I(() => [h(...)])` 范式），区分已用于 promptbox 收藏的 IconStar。
- **router.ts**：import `CfFavoritesPage from './views/CfFavoritesPage.vue'`（带 `.vue`）；routes 加 `{ path: '/cf/favorites', component: CfFavoritesPage }`。
- **App.vue**：icon import 加 `IconBookmark`；ITEMS 加 `{ label: 'cf 收藏', key: '/cf/favorites', icon: IconBookmark }`（插入位置：收藏列表附近）。activeKey longest-prefix 自动解析。

## 全局约束

- **无新增 npm 依赖**：全用现有 vue / naive-ui / vue-router / vitest 栈。
- **后端不动**：P1 已 master（231 passed），P3 只读消费 favorites/recent/random，不改任何 `backend/` 文件。
- **锁定语义延续**：P3 只读消费端点，不碰 `locked_tags`；P2 三重保险（CfSaveBody 无 locked_tags / buildPromptWithLocked / 详情页只读锁区）不受影响。
- **类型一致**：复用 P2 的 `CfListItem` / `parseEntryKey`（对象解构 `{kind,source,key}`）/ `cfAssetUrl` / ImageCard props。
- **P1 保护点保留**：router view import 带 `.vue` 后缀；App.vue `<router-view>` 外层 `<div :key="route.path">` 包装（Transition out-in 修复）不动。

## 测试策略

- **cf API**：`characterfinder.test.ts` 加 3 函数的 URL 构造断言（kind/type/source/size 参数编码正确），仿现有 searchCharacters 测试。
- **RandomPage**：源切换触发不同 API（gallery→randomImages、characters→randomCf characters、artists→randomCf artists）；卡片用对应当前源的 to/imgSrc。
- **CfFavoritesPage**：tab 切换调对 kind；渲染收藏项；toggle 后乐观移除；搜索过滤。
- **列表页最近查看区**：recent 非空时渲染卡片、空时隐藏；点击跳详情。
- **router**：`/cf/favorites` 路径注册。
- 全量回归 + `npm run build`（vue-tsc）0 exit。

## P3 不含（留 P4）

- cf 下载/同步脚本（`cf_download_covers` / `cf_import_animadex` / `cf_sync_from_sdcf`）——离线数据填充，属后端/数据层。
