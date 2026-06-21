# 整合 sd-character-finder 进 wd14-tagger-web — 设计文档

- 日期：2026-06-21
- 状态：已确认，待实现计划
- 范围：将 `sd-character-finder`（SD WebUI Gradio 扩展）的角色/艺术家百科能力整合进 `wd14-tagger-web`（FastAPI + Vue 应用），数据复制到本仓库并支持增量同步，封面图一次性下载/拷贝到本地实现完全离线。

---

## 1. 背景与目标

### 1.1 现状
- `sd-character-finder`（简称 sdcf）：SD WebUI 的 Gradio 扩展，提供角色百科（Danbooru/e621/Anima）与艺术家风格浏览。核心数据访问层（`wildcard_creator/character_db.py`、`artist_db.py`、`anima_db.py`）是纯 stdlib `sqlite3`，无重依赖，可直接移植。数据（4 个 db + csv）已提交在其 git 仓库；封面图不落地（运行时直连 CDN）。
- `wd14-tagger-web`：独立 FastAPI（`backend/`）+ Vue3 + naive-ui（`frontend/`）应用，路由模块化、依赖 `lru_cache` 工厂注入、配置走 `backend/config/settings.py` 路径常量。设计哲学是「本地运行、本地持久化、离线可用」，且有 `pack_portable.py` 面向可分发整合包。
- `animadex-data`：用户正在下载的 Anima 原始数据，已含 `characters/thumbs`（15048 个 webp）、`characters/images`（1823 个 png），`artists/*` 尚未下载。其 `import/characters.csv`(36493 行) / `artists.csv`(15880 行) 与 sdcf 的 `anima_characters.db` / `anima_artists.db` 是同一份数据（行数、字段一致），图片文件名与 db 的 `thumbname`/`imgname` 字段已验证可一一对应。

### 1.2 目标
1. 在 wd14-tagger-web 内提供角色/艺术家浏览（搜索、系列/源筛选、详情、封面）。
2. 详情页**风格与功能与现有图库 `DetailPage` 一致**：可反推、可编辑提示词、可替换图片。
3. **权威标签锁定**：角色触发词（trigger）、角色核心标签（core_tags）、画师标签（artist tag）来自 db，固定不可改；用户反推/编辑/补充的标签可编辑。
4. 随机功能（`RandomPage`）能随机到角色/艺术家。
5. 数据复制到本仓库（独立可分发），并提供**增量同步**能力，承接 sdcf 与 animadex-data 的后续更新。
6. 封面图一次性下载/拷贝到本地，应用完全离线可用。

### 1.3 非目标
- 不移植 sdcf 的实时 Danbooru 标签抓取（需外部 API 凭据，与离线哲学冲突）。
- 不实现 SD WebUI 的 `Send to txt2img`（本应用无 txt2img）；以「复制标签 / 加入提示词盒」替代。
- 不重写 sdcf 的数据访问层；原样移植，仅调整默认 db 路径。

---

## 2. 核心架构：权威层 + Overlay 层

每个角色/艺术家条目 = **db 权威数据（只读）** + **Overlay 用户数据（可编辑）**。

| 层 | 来源 | 内容 | 可变性 |
|---|---|---|---|
| 权威层 | sdcf db（复制到本仓库） | name / series / copyright / **trigger** / **core_tags** / **artist tag** / 封面图引用 / rank / source | 🔒 锁定 |
| Overlay 层 | 新增 `cf_overlay.db`（懒创建） | 反推得到的 6 类标签 + extras、自定义标签、替换图、tagger 元数据（model/阈值/raw_tags） | ✅ 可编辑 |

条目标识采用复合 key：`{kind}:{source}:{db_key}`
- `kind` ∈ `char` | `artist`
- `source` ∈ `danbooru` | `e621` | `anima`
- `db_key`：danbooru/e621 用自增 `id`；anima 用其 `character`/`artist` 文本主键（anima 库无自增 id）

示例：`char:danbooru:123`、`char:anima:001_(darling_in_the_franxx)`、`artist:danbooru:1`。

---

## 3. 数据来源与放置

数据根目录：`data/characterfinder/`（`settings.CF_DIR`）。

| 数据 | 来源 | 落地路径 | 获取方式 |
|---|---|---|---|
| Danbooru/e621 角色 | sdcf `characters.db`（59508 行） | `data/characterfinder/characters.db` | 复制 |
| Danbooru/e621 艺术家 | sdcf `artists.db`（25935 行） | `data/characterfinder/artists.db` | 复制 |
| Anima 角色 | sdcf `anima_characters.db`（36492 行） | `data/characterfinder/anima_characters.db` | 复制 |
| Anima 艺术家 | sdcf `anima_artists.db` | `data/characterfinder/anima_artists.db` | 复制 |
| Danbooru 标签表 | sdcf `danbooru_tags.csv` | `data/characterfinder/danbooru_tags.csv` | 复制 |
| Danbooru/e621 角色封面 | `characters.image_url`（downloadmost.com） | `data/characterfinder/covers/{slug}.jpg` | 下载脚本 |
| Danbooru/e621 艺术家封面 | `artists.image_url_1/2`（downloadmost.com） | `data/characterfinder/artist_covers/{slug}.jpg` | 下载脚本 |
| Anima 角色图 | `animadex-data/characters/{thumbs,images}` | `data/characterfinder/anima/characters/{文件名}` | 拷贝脚本 |
| Anima 艺术家图 | `animadex-data/artists/{thumbs,images}` | `data/characterfinder/anima/artists/{文件名}` | 拷贝脚本 |
| Overlay | 运行时生成 | `data/characterfinder/cf_overlay.db` + `overlay/` | 运行时 |
| 收藏 / 最近查看 | 运行时生成 | `data/characterfinder/favorites.json` / `recent_viewed.json` | 运行时 |

说明：
- `{slug}` 由下载脚本从 `image_url` 推导（取最后路径段，保留扩展名），保证「url → 本地文件」映射确定，从而幂等。
- Anima 图片文件名（如 `00 gundam, gundam.webp`）与 db 字段一致，拷贝后直接按 `thumbname`/`imgname` 定位，无需改名。

---

## 4. 后端设计

### 4.1 数据访问层（移植）
新建 `backend/characterfinder/`：
- `paths.py` — 统一管理 `CF_DIR` 下各路径，供 db 层与路由共用。
- `character_db.py` / `artist_db.py` / `anima_db.py` — 从 sdcf `wildcard_creator/` 原样移植，仅把 `_DEFAULT_DB` 指向 `CF_DIR` 下对应文件。保留其线程安全连接、`_migrate`、`search`/`get`/`list_series`/`count_by_source` 等方法。
- `favorites.py` — 移植 sdcf 的收藏逻辑（json 持久化），key 改用复合 entry key。
- `__init__.py`。

### 4.2 Overlay 存储
新建 `backend/storage/cf_overlay.py`，仿 `promptbox_store` 模式（sqlite + 图片落文件系统）：

```sql
CREATE TABLE IF NOT EXISTS overlay (
  entry_key      TEXT PRIMARY KEY,   -- 'char:danbooru:123'
  kind           TEXT NOT NULL,      -- 'char' | 'artist'
  custom_tags    TEXT,               -- JSON array
  categories     TEXT,               -- JSON {head:{tags,phrase,user_edited},...}（含 quality/head/clothing/view/action/scene）
  extras         TEXT,               -- JSON {tags,phrase,user_edited}
  image_override TEXT,               -- 替换图文件名（存 CF_OVERLAY_DIR/），NULL 表示用权威封面
  model          TEXT,
  gen_threshold  REAL,
  char_threshold REAL,
  raw_tags       TEXT,               -- JSON：反推原始结果（复刻图库 meta.raw_tags 语义）
  created_at     TEXT,
  updated_at     TEXT
);
```
- 仅对「用户操作过」的条目懒创建行。
- 替换图存 `data/characterfinder/overlay/{entry_key_safe}.{ext}`（entry_key 中的 `/` 等替换为安全字符）。

`backend/deps.py` 新增工厂：
```python
@lru_cache
def get_character_db(): from backend.characterfinder.character_db import CharacterDB; return CharacterDB()
@lru_cache
def get_artist_db(): ...
@lru_cache
def get_anima_character_db(): ...
@lru_cache
def get_anima_artist_db(): ...
@lru_cache
def get_cf_overlay(): from backend.storage.cf_overlay import CfOverlay; return CfOverlay()
```

### 4.3 API 路由
对齐现有 `routes_*.py`（`prefix` + `tags`）。统一前缀 `/api/cf`。

**角色**
- `GET /api/cf/characters?query=&source=anima|danbooru|e621&series=&tag_status=&favorite_only=&page=1&size=50` → `{items:[...], total}`。`source` 必填（不做跨库合并分页，前端用 tab 切换源，复刻 sdcf 做法）。item 字段统一：`{entry_key, source, name, series, trigger, core_tags, thumb_url, image_url, favorite}`（`thumb_url`/`image_url` 均为指向下述资产服务的 URL，前端不感知本地/CDN 差异；列表用 thumb，详情用 image）。
- `GET /api/cf/characters/series?source=` → 系列聚合（下拉）。
- `GET /api/cf/characters/{source}/{key}` → 权威字段 + overlay（若有）合并。
- `POST /api/cf/characters/{source}/{key}/tag` → 对当前封面图（优先 overlay 替换图，否则本地下载图）跑 `get_tagger` + `get_classifier`，结果写入 overlay，返回合并后条目。
- `POST /api/cf/characters/{source}/{key}/reclassify` → 用已存 `raw_tags` 重跑分类器（`keep` 语义同 `routes_promptbox`）。
- `PUT /api/cf/characters/{source}/{key}` → 存 overlay 的 `categories`/`extras`/`custom_tags`。
- `POST /api/cf/characters/{source}/{key}/image` → 上传替换图，存 overlay。
- `POST /api/cf/characters/{source}/{key}/favorite`、`GET /api/cf/favorites`。

**艺术家**（`/api/cf/artists/*`）同构；item 多 `image_url_1/2`、双封面、`tag`（画师标签）。

**通用**
- `GET /api/cf/recent` → 最近查看（访问详情时记录）。
- `GET /api/cf/random?type=characters|artists&source=&size=24` → 随机返回与 `ImageCard` 兼容的 item 列表（`{entry_key, source, name, thumb, tags, prompt}`），供 `RandomPage` 复用。

**封面资产服务**
- `GET /api/cf/asset?kind=&source=&key=&which=` → 优先级：① overlay 替换图（若该条目有 `image_override`，则 `which=thumb|image|1|2` 均返回替换图）② 本地下载/拷贝图 ③ **未命中则 302 重定向到原始 CDN url**（下载/拷贝未跑到该条时不裂图）。
- `which` 取值：角色用 `thumb`（缩略，列表加载快）/`image`（原图，详情）；艺术家用 `1`/`2`（双图）。Anima 角色的 `thumb` 对应 `thumbname`（webp）、`image` 对应 `imgname`（png）。

### 4.4 集成点
- `backend/config/settings.py` 新增路径常量（见 §7）。
- `backend/main.py` 注册新 router：`routes_characters`、`routes_artists`、`routes_cfassets`（在 mount `/` 之前 include）。
- `backend/models.py` 若需共享 `CategoryData` 结构则复用，否则在 cf 模块内定义等价结构。

---

## 5. 前端设计（Vue3 + naive-ui）

### 5.1 路由与导航
- `router.ts` 新增：`/characters`、`/characters/:source/:key`、`/artists`、`/artists/:source/:key`。
- `App.vue` 的 `ITEMS` 新增两项：`{ label:'角色图鉴', key:'/characters' }`、`{ label:'艺术家', key:'/artists' }`，并补对应 icon（`components/icons.ts`）。

### 5.2 API 客户端
新建 `frontend/src/api/characterfinder.ts`，仿 `client.ts` 扁平 `fetch` 风格：`searchCharacters`、`getCharacter`、`tagCharacter`、`reclassifyCharacter`、`saveCharacter`、`uploadCharacterImage`、`toggleFavorite`、`listFavorites`、`listRecent`、`randomCf(type, source)`，以及 `cfAssetUrl(kind, source, key, which)`。

### 5.3 列表页（风格一致）
- `CharactersPage.vue` / `ArtistsPage.vue`：顶部搜索框 + 源 tab（Danbooru/e621/Anima）+ 系列下拉 + 收藏过滤；下方卡片网格（`n-grid`，复用 `GalleryPage`/`RandomPage` 的列配置）。
- 卡片复用通用化后的 `ImageCard`（见 §5.5），点击进详情。

### 5.4 详情页（复用 DetailPage 布局 + 锁定标签）
`CharacterDetailPage.vue` / `ArtistDetailPage.vue` 复用 `DetailPage.vue` 的双栏结构：
- 左栏：图片预览（`n-image` contain）+ 名称 + 反推模型选择（复用 `useTagger`）+ 阈值 + 自定义标签（`n-dynamic-tags`）+ 按钮（重新反推 / 重分类 / **替换图片** / 复制 prompt / 保存）。
- 右栏：`TagEditor` × 6 类 + extras（与 `DetailPage` 一致）。

**关键差异**：
- 右栏顶部新增 **🔒 锁定标签区**：渲染角色 `trigger` + `core_tags`（艺术家为画师 `tag`，如 `@artist_name`）为只读 chip，不可增删。`buildPrompt` 时锁定标签始终前置、不可移除。
- 图片来源走 `cfAssetUrl`（经资产服务，自动本地优先 + CDN 回退）；「替换图片」调 `uploadCharacterImage`。
- 反推/重分类/保存调 cf 对应 API，结果落 overlay 后刷新页面合并态。

### 5.5 组件增强（向后兼容）
- `components/ImageCard.vue` 通用化：新增可选 props `to?: string`（点击跳转路由，默认 `/detail/{id}`）、`imgSrc?: string`（默认 `fileUrl(id, thumb)`）、`onCopyPrompt?: () => void`。不传则行为与现在完全一致（图库不受影响）。
- `components/TagEditor.vue` 新增可选 prop `lockedTags?: string[]`：在可编辑 tags 上方渲染带 🔒 的不可关闭 chip，不参与增删/拖拽。不传则无影响。

### 5.6 随机功能增强
`RandomPage.vue` 顶部加来源切换（图库 / 角色 / 艺术家，可再叠 source 子选），调用对应接口（图库走 `randomImages`，角色/艺术家走 `randomCf`），统一用 `ImageCard` 渲染。

---

## 6. 脚本（全部幂等 + 增量）

均置于 `scripts/`，Python，依赖 `requests`（见 §8）。

### 6.1 `cf_download_covers.py`（downloadmost 封面，A 类）
- 数据源：查 `characters.db` 的 `image_url`（59508）+ `artists.db` 的 `image_url_1/2`（51870）。
- 幂等：按 url 推导本地 `{slug}`，已存在且 `size>0` 跳过 → 天然增量与断点续传。
- 并发：`ThreadPoolExecutor`，并发数可配（默认 16，`settings.CF_DOWNLOAD_CONCURRENCY`），每域名分组。
- 重试：单张失败重试 N 次（默认 3，指数退避），失败写入 `data/characterfinder/covers_failed.txt`。
- 进度：打印 已下/总数/速率/ETA；支持 `--limit`、`--source`、`--resume`、`--kind characters|artists`。
- 可选 manifest：`covers_manifest.json`（url→本地+状态）。

### 6.2 `cf_import_animadex.py`（Anima 图片，从 animadex-data 拷贝）
- 源：`../animadex-data/{characters,artists}/{thumbs,images}`。
- 目标：`data/characterfinder/anima/{characters,artists}/{thumbs,images}`。
- 幂等：目标已存在且 `size>0` 跳过；**下多少拷多少，随时重跑补增量**（应对 animadex-data 仍在下载：当前 characters/thumbs 15048、images 1823、artists 0）。
- 用 `shutil.copy2` 保留 mtime；打印 拷贝/跳过/新增计数。
- 支持 `--source ../animadex-data`、`--kind characters|artists|all`、`--variant thumbs|images|all`。

### 6.3 `cf_sync_from_sdcf.py`（增量同步 db + downloadmost 封面）
- `--sdcf ../sd-character-finder`。
- 步骤：① 逐文件比对 mtime+size，变化才覆盖 db 与 csv（characters/artists/anima_*/danbooru_tags）；② 调用 `cf_download_covers` 逻辑对更新后的 db 跑增量下载（幂等）；③ 打印增量报告（新复制了哪些 db、新下了多少封面）。
- 用户工作流：**sdcf `git pull` → 跑 `cf_sync_from_sdcf.py` → 重启应用**。

---

## 7. 配置项（`backend/config/settings.py` 新增）

```python
CF_DIR = DATA_DIR / "characterfinder"
CF_COVERS_DIR = CF_DIR / "covers"
CF_ARTIST_COVERS_DIR = CF_DIR / "artist_covers"
CF_ANIMA_DIR = CF_DIR / "anima"
CF_OVERLAY_DIR = CF_DIR / "overlay"
CF_OVERLAY_DB = CF_DIR / "cf_overlay.db"
CF_FAVORITES_PATH = CF_DIR / "favorites.json"
CF_RECENT_PATH = CF_DIR / "recent_viewed.json"
SDCF_SOURCE_DIR = ROOT.parent / "sd-character-finder"   # 同步源（db）
ANIMADEX_SOURCE_DIR = ROOT.parent / "animadex-data"      # anima 图片源
CF_DOWNLOAD_CONCURRENCY = 16
CF_DOWNLOAD_RETRIES = 3
```

---

## 8. 依赖变更
- 后端 `requirements.txt`：新增 `requests>=2.31`（脚本用）。无其它新依赖（db 层纯 stdlib；tagger/classifier 复用现有）。
- 前端：无新增 npm 依赖（naive-ui / vue-router 已有）。

---

## 9. 分阶段交付
1. **P1 后端**：数据层移植 + overlay 存储 + API（角色/艺术家/资产/收藏/最近/随机）+ main.py 注册 + settings 配置。
2. **P2 前端**：API 客户端 + 列表页（复用 ImageCard）+ 详情页（复用 DetailPage 布局 + 锁定标签 + 反推/编辑/换图）+ 组件增强（ImageCard 通用化、TagEditor lockedTags）。
3. **P3 随机 + 收藏/最近**：RandomPage 来源切换；收藏夹与最近查看 UI。
4. **P4 脚本**：`cf_download_covers.py` + `cf_import_animadex.py` + `cf_sync_from_sdcf.py`。
5. **P5 验证**：离线可用性、增量同步、标签锁定不可绕过、换图/反推正确落 overlay。

---

## 10. 约束与风险
- **Anima 图片下载进度**：animadex-data 的 `artists/*` 尚未下载、`characters/images` 仅 1823。拷贝脚本须容忍部分缺失，资产服务对缺失图回退 CDN（若 animadex-data 的 url 仍指向 danbooru，则回退仅作占位，标注为待下载）。
- **anima 库无自增 id**：用 `character`/`artist` 文本主键作为 entry key 的一部分；URL 需对该文本做安全编码（`urllib.parse.quote`）。
- **文件名含特殊字符**：Anima 图片文件名含空格、逗号、方括号（如 `00 gundam, gundam.webp`、`00 qan[t], gundam.webp`）。资产服务与静态访问须正确处理（FastAPI 路径参数 + 编码，或改用 query 参数 `?name=` 传整串避免路径解析问题）。
- **标签锁定的不可绕过**：后端 `PUT`/`tag` 必须以权威 trigger/core_tags/artist 为准，忽略前端试图改写锁定字段的请求；`buildPrompt` 永远前置锁定标签。
- **并发下载礼貌**：downloadmost.com 限速，并发 + 失败重试须克制，避免被封；Anima 图片为本地拷贝无此问题。
- **db 复制占用**：4 个 db + csv ≈ 70MB，可忽略；封面图才是大头（downloadmost ~11 万张 + animadex 数万张，数 GB），由脚本按需/分批下。

---

## 11. 已确认决策
- 功能范围：**完整移植**（角色+艺术家+收藏+最近查看+标签插入/复制；去实时 Danbooru 抓取、去 Send-to-txt2img）。
- 封面下载：**全部下载**（downloadmost 封面一次性下完；anima 靠 animadex-data 拷贝）。
- 数据放置：**复制 + 增量同步脚本**（独立可分发，契合 portable 定位）。
- Anima 数据来源：**sdcf db（已完整）+ animadex-data 图片（拷贝，下多少拷多少）**，不抓 danbooru。
- 第 6 节原 Anima 封面方案选 **(a)**（先跳过抓取），实际由 animadex-data 拷贝替代，等价且更优。
