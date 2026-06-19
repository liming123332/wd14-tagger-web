# UI 高级化（深浅双模 + 侧边栏骨架）设计

## 目标
把当前「简陋」的默认 naive-ui 界面升级为精致、现代、专业的视觉风格，支持深色/浅色双主题切换（默认跟随系统）。**只改视觉与布局层，不改任何功能逻辑与数据结构。**

## 背景与现状（简陋根源）
- `App.vue` 的 `n-config-provider` **无任何主题覆盖**（naive-ui 默认白底绿/蓝）。
- 顶部是**纯文字水平菜单**（上传/图库/随机/收藏列表/提示词收藏/设置），无图标、无品牌。
- 图库卡片 `ImageCard.vue` 用 **emoji 当图标**（📋⬇），无阴影层次。
- 无全局视觉语言：无统一字体、间距、圆角、动效。
- 无暗色模式。

技术栈保持不变：**Vue 3 + naive-ui + vite**，不引入 Tailwind 或新 UI 框架。

## 方案概述
1. **主题系统**：naive-ui `themeOverrides` 深度定制 + 三态切换（自动/亮/暗）。
2. **布局骨架**：左侧固定侧边栏（品牌/菜单/切换钮）+ 右侧主区（工具条 + 内容容器）。
3. **组件改造**：卡片、筛选栏、详情页、按钮/标签全站统一视觉语言。
4. **图标方案**：内联 SVG 图标组件（零新依赖），替换所有 emoji。
5. **排版与动效**：统一字体栈、间距节奏、hover/切换过渡。

---

## 详细设计

### 1. 主题系统（深浅双模）

**实现**：`App.vue` 的 `n-config-provider` 绑定 `:theme`（`darkTheme | null`）与 `:theme-overrides`。

**配色（色值）**：

| 用途 | 深色 | 浅色 |
|---|---|---|
| 页面底色 | `#15171c` | `#fafafa` |
| 面板/卡片 | `#1c1f26` | `#ffffff` |
| 侧栏 | `#111317` | `#ffffff` |
| 边框 | `#2a2e37` | `#e5e7eb` |
| 主文字 | `#e5e7eb` | `#1f2937` |
| 次文字 | `#9ca3af` | `#6b7280` |
| 主色（强调） | `#6366f1` | `#6366f1` |
| 主色 hover | `#4f46e5` | `#4f46e5` |

**themeOverrides 关键项**：`common.primaryColor`、`common.borderRadius`（`10px`）、`common.bodyColor`（底色）、`common.cardColor`（面板）、`common.textColorBase`；以及 `Card`/`Button`/`Tag`/`Menu` 等组件级覆盖（圆角、阴影、hover 态）。

**切换逻辑（`composables/useTheme.ts`）**：
- 状态 `mode: 'auto' | 'light' | 'dark'`，默认 `'auto'`。
- `auto`：读 `window.matchMedia('(prefers-color-scheme: dark)')`，并监听变化。
- 解析出的有效主题 `effective: 'light' | 'dark'` 传给 `n-config-provider`。
- `mode` 持久化到 `localStorage`（key: `wd14.theme`）。
- 暴露 `setMode(m)`。

### 2. 布局骨架（左侧边栏）

`App.vue` 重构为：
```
n-config-provider(:theme :theme-overrides)
  n-message-provider / n-dialog-provider
    n-layout(has-sider)
      n-layout-sider(宽 220, 固定)   ← 侧栏
        品牌区  ◆ WD14 标注
        n-menu(mode=vertical, 图标+文字, 6 项)
        底部: 主题切换钮(三态) + 版本号
      n-layout                         ← 主区
        工具条(页面标题 + 右侧操作槽, 含 BatchBadge)
        内容容器(router-view, 统一内边距, 最大宽度)
```

- 菜单项：上传 / 图库 / 随机 / 收藏列表 / 提示词收藏 / 设置，每项配 SVG 图标，活跃路由项高亮（`n-menu` 的 `value` 绑定当前路由）。
- 工具条：左侧显示当前页标题（由路由 meta 或映射得到），右侧放 `BatchBadge` 等全局操作。
- 响应式：窄屏（<768px）侧栏可折叠为图标条（`n-layout-sider` 的 `collapsed`）。

### 3. 组件改造（全站统一视觉语言）

- **`ImageCard.vue`（图库卡片）**：圆角 + `hover` 上浮（`transform: translateY(-2px)`）+ 阴影加深；左上角操作按钮 emoji → SVG 图标（复制/下载）；缩略图容器统一圆角与底色；标签更精致（更小圆角、次色边框）。
- **筛选栏（`GalleryPage` / `CollectionListPage`）**：用 `n-card`/面板包裹，「日期/标签/提示词」改为标签式 label（`n-tag` 或加粗小标题），控件统一 `size` 与间距。
- **详情页（`DetailPage` / `PromptboxDetailPage`）**：左右栅格保留；左右两栏都用卡片包裹并统一间距；图片区加深底容器（`#0f1115` 深色 / `#f0f0f2` 浅色）衬出图片；按钮组统一风格。
- **按钮/标签/输入**：统一主色、圆角、`hover` 动效（0.2s ease）。
- **`TagEditor` / `BatchBadge` / `BatchBars`**：套用全局主题，随 themeOverrides 自动适配，必要时微调。

### 4. 图标方案（内联 SVG，零依赖）

新建 `components/icons/`，每个图标一个极小组件（或一个 `icons/index.ts` 统一导出）。统一 `stroke` 线性风格（24×24 viewBox，`stroke="currentColor"`，`stroke-width=1.8`），随文字色继承。

**图标清单**：
- 导航：`IconUpload` `IconGallery`(网格) `IconRandom`(洗牌) `IconStar` `IconEdit`(铅笔) `IconSettings`(齿轮)
- 操作：`IconCopy` `IconDownload` `IconTrash` `IconSearch` `IconClose` `IconPlus` `IconImage`
- 主题：`IconSun` `IconMoon` `IconMonitor`(auto)

替换 `ImageCard.vue` 的 📋(→IconCopy) ⬇(→IconDownload) 及菜单文字旁的图标。**不安装 `@vicons`**。

### 5. 排版与动效

- **字体栈**：`-apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif`，在 `main.ts` 注入的全局样式中设定 `body`。
- **间距节奏**：4 / 8 / 12 / 16 / 24 / 32 px。
- **过渡**：卡片/按钮 hover `0.2s ease`；路由切换 `<router-view>` 包 `<Transition>` 淡入（0.15s）。
- **圆角**：统一 `10px`（卡片/面板）、`6px`（按钮/标签/输入）。

### 6. 范围与不动点

- **改**：`App.vue` 骨架、全局主题、`ImageCard`、各页面模板的视觉/布局层、emoji→SVG。
- **不改**：任何 API 调用、数据结构、业务逻辑、路由路径、后端。
- **全站套用**：图库 / 上传 / 两类详情 / 收藏列表 / 提示词工作台 / 随机 / 设置 / 批次详情，均落在统一骨架与主题下。

---

## 受影响文件清单

**新增**：
- `frontend/src/composables/useTheme.ts` — 主题状态与切换
- `frontend/src/styles/theme.ts` — light/dark `themeOverrides` 配置
- `frontend/src/styles/global.css` — 全局字体/底色/过渡
- `frontend/src/components/icons/*` — SVG 图标组件集
- 对应测试：`__tests__/useTheme.test.ts`、icons 冒烟测试

**修改**：
- `frontend/src/App.vue` — 主题 provider + 侧栏骨架（重写模板）
- `frontend/src/main.ts` — 引入 `global.css`
- `frontend/src/components/ImageCard.vue` — 卡片视觉 + SVG 图标
- `frontend/src/views/GalleryPage.vue` — 筛选栏面板化
- `frontend/src/views/DetailPage.vue`、`PromptboxDetailPage.vue` — 详情页卡片化/图片容器
- `frontend/src/views/CollectionListPage.vue`、`PromptBoxPage.vue`、`UploadPage.vue`、`RandomPage.vue`、`SettingsPage.vue`、`BatchDetailPage.vue` — 套用骨架，去 emoji/内联 label 统一
- `frontend/src/components/TagEditor.vue`、`BatchBadge.vue`、`BatchBars.vue` — 随主题微调
- 相关测试调整：`App.test.ts`（菜单结构变 vertical）、各页面测试（mock 不变，断言按需调整）

## 测试策略
- **`useTheme`**：`mode` 默认 `auto`；`setMode` 写 `localStorage`；`auto` 跟随 `matchMedia` 并响应变化；`effective` 正确派生（用 `vi.stubGlobal` 模拟 `matchMedia`）。
- **`App`**：渲染 6 个菜单项 + 主题切换钮；点击切换钮改 `mode`。
- **icons**：冒烟渲染若干图标含 `<svg>`。
- **既有页面测试**：naive-ui 仍 `importActual` mock，仅调整因布局变化导致的 DOM 断言（如菜单由水平变垂直、emoji 文本替换为图标组件）。
- **回归**：`npx vitest run` 全绿；`npx vue-tsc -b` exit 0；`npm run build` 成功；浏览器人工核验深/浅两套 + 各页面。

## 非目标（YAGNI）
- 不做完整的可自定义主题色板（用户自选主色）。
- 不做多语言/i18n。
- 不做移动端原生适配（仅窄屏侧栏折叠这一基础响应式）。
- 不引入 Tailwind / 设计系统库 / 图标包依赖。
- 不改后端与数据。
