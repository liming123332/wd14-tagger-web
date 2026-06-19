# UI 高级化（深浅双模 + 侧边栏）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把默认 naive-ui 界面升级为深/浅双模 + 左侧边栏骨架的精致风格，全站统一视觉语言，不改任何功能与数据。

**Architecture:** 在 `App.vue` 用 `n-config-provider` 绑定 `darkTheme`/`null` + `themeOverrides`（`styles/theme.ts`），主题状态由 `composables/useTheme.ts` 管理（三态 auto/light/dark + localStorage + 系统监听）；骨架改为 `n-layout has-sider`（固定侧栏含品牌/菜单/切换钮）；emoji 全部替换为零依赖的内联 SVG 图标集（`components/icons.ts`）；各页面套用统一卡片/间距/hover 语言。

**Tech Stack:** Vue 3 + naive-ui + vite + vitest + vue-tsc。不引入 Tailwind / 新 UI 框架 / 图标包。

## Global Constraints

- 技术栈不变：Vue3 + naive-ui，**不装 `@vicons`、不装 Tailwind**。
- 主色统一 `#6366f1`（紫蓝），hover `#4f46e5`。
- 圆角：卡片/面板 `10px`，按钮/标签/输入 `6px`。
- 字体栈：`-apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif`。
- 间距节奏：4 / 8 / 12 / 16 / 24 / 32 px。
- **不改**任何 API 调用、数据结构、路由路径、后端。
- 所有命令在 `frontend/` 目录执行：`cd /i/trae/wd14/wd14-tagger-web/frontend && ...`；git 用 `git -C /i/trae/wd14/wd14-tagger-web`。
- 在新分支 `feat/ui-premium-redesign` 上开发（`git -C /i/trae/wd14/wd14-tagger-web checkout -b feat/ui-premium-redesign`，开工前执行一次）。
- TDD：每个任务先写测试 → 跑 RED → 实现 → 跑 GREEN → commit。

---

## File Structure

**新增**
- `frontend/src/styles/theme.ts` — light/dark `GlobalThemeOverrides` 配置（纯数据）。
- `frontend/src/styles/global.css` — 全局字体/底色/路由淡入。
- `frontend/src/composables/useTheme.ts` — 主题三态状态 + localStorage + 系统监听。
- `frontend/src/components/icons.ts` — 内联 SVG 函数式图标组件集。
- 测试：`__tests__/theme.test.ts`、`useTheme.test.ts`、`icons.test.ts`、`GalleryPage.test.ts`。

**修改**
- `frontend/src/main.ts` — 引入 `global.css`。
- `frontend/src/App.vue` — 主题 provider + 侧栏骨架（模板重写）。
- `frontend/src/__tests__/App.test.ts` — 补骨架相关 stubs。
- `frontend/src/components/ImageCard.vue` — emoji→SVG 图标 + hover 样式。
- `frontend/src/views/GalleryPage.vue` — 筛选栏面板化。
- `frontend/src/views/DetailPage.vue`、`PromptboxDetailPage.vue` — 图片区深底容器。
- `frontend/src/components/BatchBadge.vue` — emoji→SVG（收尾）。

---

### Task 1: 主题配置 theme.ts

**Files:**
- Create: `frontend/src/styles/theme.ts`
- Test: `frontend/src/__tests__/theme.test.ts`

**Interfaces:**
- Produces: `lightOverrides: GlobalThemeOverrides`、`darkOverrides: GlobalThemeOverrides`（后续 App.vue 消费）。

- [ ] **Step 1: 写失败测试**

`frontend/src/__tests__/theme.test.ts`:
```ts
import { describe, it, expect } from 'vitest'
import { lightOverrides, darkOverrides } from '../styles/theme'

describe('theme overrides', () => {
  it('主色紫蓝 #6366f1，深浅一致', () => {
    expect(lightOverrides.common?.primaryColor).toBe('#6366f1')
    expect(darkOverrides.common?.primaryColor).toBe('#6366f1')
  })
  it('深色底 #15171c / 卡片 #1c1f26；浅色底 #fafafa / 卡片 #ffffff', () => {
    expect(darkOverrides.common?.bodyColor).toBe('#15171c')
    expect(darkOverrides.common?.cardColor).toBe('#1c1f26')
    expect(lightOverrides.common?.bodyColor).toBe('#fafafa')
    expect(lightOverrides.common?.cardColor).toBe('#ffffff')
  })
  it('字体栈含 Microsoft YaHei', () => {
    expect(lightOverrides.common?.fontFamily).toContain('Microsoft YaHei')
  })
  it('卡片圆角 10px，按钮 6px', () => {
    expect(lightOverrides.Card?.borderRadius).toBe('10px')
    expect(lightOverrides.Button?.borderRadiusSmall).toBe('6px')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /i/trae/wd14/wd14-tagger-web/frontend && npx vitest run src/__tests__/theme.test.ts`
Expected: FAIL — `Failed to resolve import "../styles/theme"`

- [ ] **Step 3: 实现 theme.ts**

`frontend/src/styles/theme.ts`:
```ts
import type { GlobalThemeOverrides } from 'naive-ui'

const FONT = '-apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif'

export const lightOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#6366f1',
    primaryColorHover: '#4f46e5',
    primaryColorPressed: '#4338ca',
    borderRadius: '10px',
    bodyColor: '#fafafa',
    cardColor: '#ffffff',
    modalColor: '#ffffff',
    textColorBase: '#1f2937',
    textColor1: '#1f2937',
    textColor2: '#4b5563',
    textColor3: '#6b7280',
    borderColor: '#e5e7eb',
    dividerColor: '#eceef1',
    fontFamily: FONT,
  },
  Card: { borderRadius: '10px', color: '#ffffff' },
  Button: { borderRadiusMedium: '6px', borderRadiusSmall: '6px', borderRadiusTiny: '6px' },
  Tag: { borderRadius: '6px' },
  Input: { borderRadius: '6px' },
  Select: { peers: { InternalSelection: { borderRadius: '6px' } } },
  Menu: { itemHeight: '40px' },
}

export const darkOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#6366f1',
    primaryColorHover: '#4f46e5',
    primaryColorPressed: '#4338ca',
    borderRadius: '10px',
    bodyColor: '#15171c',
    cardColor: '#1c1f26',
    modalColor: '#1c1f26',
    textColorBase: '#e5e7eb',
    textColor1: '#e5e7eb',
    textColor2: '#c9cdd4',
    textColor3: '#9ca3af',
    borderColor: '#2a2e37',
    dividerColor: '#262a32',
    fontFamily: FONT,
  },
  Card: { borderRadius: '10px', color: '#1c1f26' },
  Button: { borderRadiusMedium: '6px', borderRadiusSmall: '6px', borderRadiusTiny: '6px' },
  Tag: { borderRadius: '6px' },
  Input: { borderRadius: '6px' },
  Select: { peers: { InternalSelection: { borderRadius: '6px' } } },
  Menu: { itemHeight: '40px', color: '#111317', itemTextColor: '#9ca3af', itemTextColorActive: '#e5e7eb', itemColorActive: '#262a32' },
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd /i/trae/wd14/wd14-tagger-web/frontend && npx vitest run src/__tests__/theme.test.ts`
Expected: PASS（4 tests）

- [ ] **Step 5: 提交**

```bash
git -C /i/trae/wd14/wd14-tagger-web add frontend/src/styles/theme.ts frontend/src/__tests__/theme.test.ts
git -C /i/trae/wd14/wd14-tagger-web commit -m "feat(ui): theme.ts 深/浅 themeOverrides 配置"
```

---

### Task 2: useTheme composable

**Files:**
- Create: `frontend/src/composables/useTheme.ts`
- Test: `frontend/src/__tests__/useTheme.test.ts`

**Interfaces:**
- Produces: `useTheme()` → `{ mode: Ref<'auto'|'light'|'dark'>, effective: ComputedRef<'light'|'dark'>, setMode(m): void }`。App.vue 消费。

- [ ] **Step 1: 写失败测试**

`frontend/src/__tests__/useTheme.test.ts`:
```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'

function mockMatchMedia(dark: boolean) {
  const listeners: ((e: any) => void)[] = []
  vi.stubGlobal('matchMedia', vi.fn().mockImplementation(() => ({
    matches: dark,
    addEventListener: (_: string, cb: (e: any) => void) => listeners.push(cb),
    removeEventListener: () => {},
  })))
  return listeners
}

describe('useTheme', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.unstubAllGlobals()
    vi.resetModules()
  })

  it('默认 auto；系统亮→effective light', async () => {
    mockMatchMedia(false)
    const { useTheme } = await import('../composables/useTheme')
    const { mode, effective } = useTheme()
    expect(mode.value).toBe('auto')
    expect(effective.value).toBe('light')
  })

  it('auto + 系统暗→effective dark', async () => {
    mockMatchMedia(true)
    const { useTheme } = await import('../composables/useTheme')
    const { effective } = useTheme()
    expect(effective.value).toBe('dark')
  })

  it('setMode 写 localStorage', async () => {
    mockMatchMedia(false)
    const { useTheme } = await import('../composables/useTheme')
    const { setMode } = useTheme()
    setMode('dark')
    expect(localStorage.getItem('wd14.theme')).toBe('dark')
  })

  it('启动读 localStorage 覆盖默认', async () => {
    localStorage.setItem('wd14.theme', 'dark')
    mockMatchMedia(false)
    const { useTheme } = await import('../composables/useTheme')
    const { mode } = useTheme()
    expect(mode.value).toBe('dark')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /i/trae/wd14/wd14-tagger-web/frontend && npx vitest run src/__tests__/useTheme.test.ts`
Expected: FAIL — `Failed to resolve import "../composables/useTheme"`

- [ ] **Step 3: 实现 useTheme.ts**

`frontend/src/composables/useTheme.ts`:
```ts
import { ref, computed } from 'vue'

export type ThemeMode = 'auto' | 'light' | 'dark'
const STORAGE_KEY = 'wd14.theme'

const mode = ref<ThemeMode>('auto')
const sysTick = ref(0)        // auto 模式下系统变化时递增以刷新 effective
let inited = false

function systemDark(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

function init() {
  if (inited || typeof window === 'undefined' || !window.matchMedia) return
  inited = true
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved === 'auto' || saved === 'light' || saved === 'dark') mode.value = saved
  const mq = window.matchMedia('(prefers-color-scheme: dark)')
  mq.addEventListener?.('change', () => { sysTick.value++ })
}

export function useTheme() {
  init()
  const effective = computed<'light' | 'dark'>(() => {
    void sysTick.value
    return mode.value === 'auto' ? (systemDark() ? 'dark' : 'light') : mode.value
  })
  function setMode(m: ThemeMode) {
    mode.value = m
    try { localStorage.setItem(STORAGE_KEY, m) } catch { /* 忽略隐私模式 */ }
  }
  return { mode, effective, setMode }
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd /i/trae/wd14/wd14-tagger-web/frontend && npx vitest run src/__tests__/useTheme.test.ts`
Expected: PASS（4 tests）

- [ ] **Step 5: 提交**

```bash
git -C /i/trae/wd14/wd14-tagger-web add frontend/src/composables/useTheme.ts frontend/src/__tests__/useTheme.test.ts
git -C /i/trae/wd14/wd14-tagger-web commit -m "feat(ui): useTheme 三态主题状态 + localStorage + 系统监听"
```

---

### Task 3: SVG 图标集 icons.ts

**Files:**
- Create: `frontend/src/components/icons.ts`
- Test: `frontend/src/__tests__/icons.test.ts`

**Interfaces:**
- Produces: `IconUpload / IconGallery / IconRandom / IconStar / IconEdit / IconSettings / IconCheck / IconCopy / IconDownload / IconTrash / IconSearch / IconClose / IconPlus / IconImage / IconSun / IconMoon / IconMonitor`（均为函数式图标组件，App.vue / ImageCard.vue / BatchBadge.vue 消费）。

- [ ] **Step 1: 写失败测试**

`frontend/src/__tests__/icons.test.ts`:
```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { h } from 'vue'
import {
  IconUpload, IconGallery, IconCheck, IconCopy, IconDownload,
  IconSun, IconMoon, IconMonitor,
} from '../components/icons'

const wrap = (I: any) => mount({ render: () => h(I) })

describe('icons', () => {
  it.each([
    ['IconUpload', IconUpload], ['IconGallery', IconGallery],
    ['IconCheck', IconCheck], ['IconCopy', IconCopy], ['IconDownload', IconDownload],
  ])('%s 渲染一个 svg', (_name, I) => {
    expect(wrap(I).find('svg').exists()).toBe(true)
  })
  it('svg 用 currentColor 描边（随文字色继承）', () => {
    expect(wrap(IconCopy).find('svg').attributes('stroke')).toBe('currentColor')
  })
  it('主题三图标都存在', () => {
    expect(wrap(IconSun).find('svg').exists()).toBe(true)
    expect(wrap(IconMoon).find('svg').exists()).toBe(true)
    expect(wrap(IconMonitor).find('svg').exists()).toBe(true)
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /i/trae/wd14/wd14-tagger-web/frontend && npx vitest run src/__tests__/icons.test.ts`
Expected: FAIL — `Failed to resolve import "../components/icons"`

- [ ] **Step 3: 实现 icons.ts**

`frontend/src/components/icons.ts`（Feather/Lucide 风格线性图标，`stroke=currentColor`，24×24）:
```ts
import { h, type FunctionalComponent } from 'vue'

const S = {
  viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
  'stroke-width': 1.8, 'stroke-linecap': 'round', 'stroke-linejoin': 'round',
  width: '1em', height: '1em',
} as Record<string, any>

const I = (children: any[]): FunctionalComponent => (() => h('svg', S, children)) as any

export const IconUpload = I([
  h('path', { d: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4' }),
  h('polyline', { points: '17 8 12 3 7 8' }),
  h('line', { x1: 12, y1: 3, x2: 12, y2: 15 }),
])
export const IconGallery = I([
  h('rect', { x: 3, y: 3, width: 7, height: 7, rx: 1 }),
  h('rect', { x: 14, y: 3, width: 7, height: 7, rx: 1 }),
  h('rect', { x: 14, y: 14, width: 7, height: 7, rx: 1 }),
  h('rect', { x: 3, y: 14, width: 7, height: 7, rx: 1 }),
])
export const IconRandom = I([
  h('polyline', { points: '16 3 21 3 21 8' }),
  h('line', { x1: 4, y1: 20, x2: 21, y2: 3 }),
  h('polyline', { points: '21 16 21 21 16 21' }),
  h('line', { x1: 15, y1: 15, x2: 21, y2: 21 }),
  h('line', { x1: 4, y1: 4, x2: 9, y2: 9 }),
])
export const IconStar = I([
  h('polygon', { points: '12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2' }),
])
export const IconEdit = I([
  h('path', { d: 'M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7' }),
  h('path', { d: 'M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z' }),
])
export const IconSettings = I([
  h('circle', { cx: 12, cy: 12, r: 3 }),
  h('path', { d: 'M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z' }),
])
export const IconCheck = I([
  h('polyline', { points: '20 6 9 17 4 12' }),
])
export const IconCopy = I([
  h('rect', { x: 9, y: 9, width: 13, height: 13, rx: 2 }),
  h('path', { d: 'M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1' }),
])
export const IconDownload = I([
  h('path', { d: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4' }),
  h('polyline', { points: '7 10 12 15 17 10' }),
  h('line', { x1: 12, y1: 15, x2: 12, y2: 3 }),
])
export const IconTrash = I([
  h('polyline', { points: '3 6 5 6 21 6' }),
  h('path', { d: 'M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2' }),
])
export const IconSearch = I([
  h('circle', { cx: 11, cy: 11, r: 8 }),
  h('line', { x1: 21, y1: 21, x2: 16.65, y2: 16.65 }),
])
export const IconClose = I([
  h('line', { x1: 18, y1: 6, x2: 6, y2: 18 }),
  h('line', { x1: 6, y1: 6, x2: 18, y2: 18 }),
])
export const IconPlus = I([
  h('line', { x1: 12, y1: 5, x2: 12, y2: 19 }),
  h('line', { x1: 5, y1: 12, x2: 19, y2: 12 }),
])
export const IconImage = I([
  h('rect', { x: 3, y: 3, width: 18, height: 18, rx: 2 }),
  h('circle', { cx: 8.5, cy: 8.5, r: 1.5 }),
  h('polyline', { points: '21 15 16 10 5 21' }),
])
export const IconSun = I([
  h('circle', { cx: 12, cy: 12, r: 5 }),
  h('line', { x1: 12, y1: 1, x2: 12, y2: 3 }),
  h('line', { x1: 12, y1: 21, x2: 12, y2: 23 }),
  h('line', { x1: 4.22, y1: 4.22, x2: 5.64, y2: 5.64 }),
  h('line', { x1: 18.36, y1: 18.36, x2: 19.78, y2: 19.78 }),
  h('line', { x1: 1, y1: 12, x2: 3, y2: 12 }),
  h('line', { x1: 21, y1: 12, x2: 23, y2: 12 }),
  h('line', { x1: 4.22, y1: 19.78, x2: 5.64, y2: 18.36 }),
  h('line', { x1: 18.36, y1: 5.64, x2: 19.78, y2: 4.22 }),
])
export const IconMoon = I([
  h('path', { d: 'M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z' }),
])
export const IconMonitor = I([
  h('rect', { x: 2, y: 3, width: 20, height: 14, rx: 2 }),
  h('line', { x1: 8, y1: 21, x2: 16, y2: 21 }),
  h('line', { x1: 12, y1: 17, x2: 12, y2: 21 }),
])
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd /i/trae/wd14/wd14-tagger-web/frontend && npx vitest run src/__tests__/icons.test.ts`
Expected: PASS

- [ ] **Step 5: vue-tsc 类型检查**

Run: `cd /i/trae/wd14/wd14-tagger-web/frontend && npx vue-tsc -b`
Expected: exit 0

- [ ] **Step 6: 提交**

```bash
git -C /i/trae/wd14/wd14-tagger-web add frontend/src/components/icons.ts frontend/src/__tests__/icons.test.ts
git -C /i/trae/wd14/wd14-tagger-web commit -m "feat(ui): 内联 SVG 图标集 icons.ts（零依赖，替换 emoji）"
```

---

### Task 4: App.vue 侧栏骨架 + 全局样式

**Files:**
- Create: `frontend/src/styles/global.css`
- Modify: `frontend/src/main.ts`
- Modify: `frontend/src/App.vue`（模板重写）
- Modify: `frontend/src/__tests__/App.test.ts`

**Interfaces:**
- Consumes: `lightOverrides/darkOverrides`（Task 1）、`useTheme`（Task 2）、`icons`（Task 3）。
- Produces: 全站统一骨架（侧栏 + 主区工具条），所有页面落在其内。

- [ ] **Step 1: 写失败测试（更新 App.test.ts）**

替换 `frontend/src/__tests__/App.test.ts` 全文为：
```ts
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ path: '/gallery' }),
}))

import App from '../App.vue'
import BatchBadge from '../components/BatchBadge.vue'

const stubs = {
  NConfigProvider: { template: '<slot/>' },
  NMessageProvider: { template: '<slot/>' },
  NDialogProvider: { template: '<slot/>' },
  NLayout: { template: '<slot/>' },
  NLayoutSider: { template: '<div class="sider"><slot/></div>' },
  NLayoutContent: { template: '<div class="content-wrap"><slot/></div>' },
  NMenu: { template: '<div class="n-menu"/>' },
  NButton: { template: '<button @click="$emit(\'click\')"><slot/></button>' },
  NIcon: { template: '<i/>' },
}

describe('App', () => {
  it('渲染侧栏骨架与 BatchBadge', () => {
    const w = mount(App, { global: { stubs } })
    expect(w.find('.sider').exists()).toBe(true)
    expect(w.findComponent(BatchBadge).exists()).toBe(true)
  })
  it('侧栏含品牌标识', () => {
    const w = mount(App, { global: { stubs } })
    expect(w.find('.brand').text()).toContain('WD14')
  })
  it('工具条显示当前页标题（图库）', () => {
    const w = mount(App, { global: { stubs } })
    expect(w.find('.topbar').text()).toContain('图库')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /i/trae/wd14/wd14-tagger-web/frontend && npx vitest run src/__tests__/App.test.ts`
Expected: FAIL — `.sider` / `.brand` 找不到（旧 App.vue 是顶栏）

- [ ] **Step 3: 创建 global.css**

`frontend/src/styles/global.css`:
```css
:root { color-scheme: light dark; }
html, body, #app { height: 100%; margin: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
```

- [ ] **Step 4: main.ts 引入 global.css**

`frontend/src/main.ts` 改为：
```ts
import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import './styles/global.css'
createApp(App).use(router).mount('#app')
```

- [ ] **Step 5: 重写 App.vue**

`frontend/src/App.vue` 全文：
```vue
<script setup lang="ts">
import { computed, h } from 'vue'
import {
  NConfigProvider, NMessageProvider, NDialogProvider, NLayout, NLayoutSider,
  NLayoutContent, NMenu, NButton, NIcon, darkTheme,
} from 'naive-ui'
import type { GlobalTheme } from 'naive-ui'
import { useRouter, useRoute } from 'vue-router'
import BatchBadge from './components/BatchBadge.vue'
import { lightOverrides, darkOverrides } from './styles/theme'
import { useTheme } from './composables/useTheme'
import {
  IconUpload, IconGallery, IconRandom, IconStar, IconEdit, IconSettings,
  IconSun, IconMoon, IconMonitor,
} from './components/icons'

const router = useRouter()
const route = useRoute()
const { mode, effective, setMode } = useTheme()

const theme = computed<GlobalTheme | null>(() => (effective.value === 'dark' ? darkTheme : null))
const overrides = computed(() => (effective.value === 'dark' ? darkOverrides : lightOverrides))

const ITEMS = [
  { label: '上传', key: '/upload', icon: IconUpload },
  { label: '图库', key: '/gallery', icon: IconGallery },
  { label: '随机', key: '/random', icon: IconRandom },
  { label: '收藏列表', key: '/collections', icon: IconStar },
  { label: '提示词收藏', key: '/promptbox', icon: IconEdit },
  { label: '设置', key: '/settings', icon: IconSettings },
] as const

const menuOptions = ITEMS.map(it => ({
  label: it.label, key: it.key,
  icon: () => h(NIcon, { component: it.icon }),
}))
const activeKey = computed(() => {
  const path = route.path
  const hit = ITEMS.map(i => i.key).filter(k => path.startsWith(k))
    .sort((a, b) => b.length - a.length)[0]
  return hit || '/gallery'
})
function go(key: string) { router.push(key) }

const currentTitle = computed(() => ITEMS.find(i => i.key === activeKey.value)?.label || '')

const themeIcon = computed(() =>
  mode.value === 'light' ? IconSun : mode.value === 'dark' ? IconMoon : IconMonitor)
const themeLabel = computed(() => mode.value === 'auto' ? '自动' : mode.value === 'light' ? '浅色' : '深色')
function cycleTheme() {
  const order = ['auto', 'light', 'dark'] as const
  setMode(order[(order.indexOf(mode.value) + 1) % order.length])
}
</script>

<template>
  <n-config-provider :theme="theme" :theme-overrides="overrides">
    <n-message-provider>
      <n-dialog-provider>
        <n-layout has-sider style="min-height:100vh">
          <n-layout-sider bordered :width="220" :collapsed-width="64" show-trigger collapse-mode="width"
                          :native-scrollbar="false"
                          content-style="display:flex;flex-direction:column;min-height:100%">
            <div class="brand">◆ WD14 标注</div>
            <n-menu :value="activeKey" :options="menuOptions" :collapsed-width="64"
                    @update:value="go" style="flex:1" />
            <div class="sider-foot">
              <n-button quaternary size="small" block @click="cycleTheme">
                <template #icon><n-icon :component="themeIcon" /></template>
                {{ themeLabel }}
              </n-button>
            </div>
          </n-layout-sider>
          <n-layout-content :native-scrollbar="false">
            <div class="topbar">
              <span class="title">{{ currentTitle }}</span>
              <BatchBadge />
            </div>
            <div class="content">
              <router-view v-slot="{ Component }">
                <transition name="fade" mode="out-in">
                  <component :is="Component" />
                </transition>
              </router-view>
            </div>
          </n-layout-content>
        </n-layout>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<style scoped>
.brand { font-size: 15px; font-weight: 700; padding: 16px 18px 8px; letter-spacing: 0.5px }
.sider-foot { padding: 8px 10px 12px; border-top: 1px solid var(--n-border-color, #eceef1) }
.topbar {
  height: 48px; padding: 0 20px; display: flex; align-items: center; justify-content: space-between;
  border-bottom: 1px solid rgba(128,128,128,0.12); position: sticky; top: 0; z-index: 10;
  backdrop-filter: blur(6px);
}
.topbar .title { font-size: 15px; font-weight: 600 }
.content { padding: 16px 20px 32px; max-width: 1600px; margin: 0 auto }
</style>
```

- [ ] **Step 6: 跑测试确认通过**

Run: `cd /i/trae/wd14/wd14-tagger-web/frontend && npx vitest run src/__tests__/App.test.ts`
Expected: PASS（3 tests）

- [ ] **Step 7: vue-tsc + build**

Run: `cd /i/trae/wd14/wd14-tagger-web/frontend && npx vue-tsc -b && npm run build`
Expected: exit 0

- [ ] **Step 8: 提交**

```bash
git -C /i/trae/wd14/wd14-tagger-web add frontend/src/App.vue frontend/src/main.ts frontend/src/styles/global.css frontend/src/__tests__/App.test.ts
git -C /i/trae/wd14/wd14-tagger-web commit -m "feat(ui): App 侧栏骨架 + 主题 provider + 全局样式"
```

---

### Task 5: ImageCard 视觉升级（emoji → SVG）

**Files:**
- Modify: `frontend/src/components/ImageCard.vue`

**Interfaces:**
- Consumes: `IconCopy / IconDownload`（Task 3）。
- 说明：现有 `ImageCard.test.ts` 按 `title` 属性定位按钮、不依赖 emoji 文本，故换图标不破坏既有测试，本任务以"既有测试不回归"为验证。

- [ ] **Step 1: 跑现有测试建立基线（应通过）**

Run: `cd /i/trae/wd14/wd14-tagger-web/frontend && npx vitest run src/__tests__/ImageCard.test.ts`
Expected: PASS（5 tests，当前）

- [ ] **Step 2: 改 ImageCard.vue**

把 `<script setup>` 的 naive-ui 导入行下方新增图标导入（在 `import { fileUrl } ...` 之后加一行）：
```ts
import { IconCopy, IconDownload } from '../components/icons'
```
把模板里两个按钮的 emoji 换成图标组件：
```html
    <div class="actions">
      <n-button size="tiny" circle secondary @click.stop="copy" title="复制完整 prompt"><IconCopy/></n-button>
      <n-button size="tiny" circle secondary @click.stop="download" title="下载原图"><IconDownload/></n-button>
    </div>
```
在 `<style scoped>` 末尾追加卡片 hover 上浮：
```css
.thumb :deep(.n-card) { transition: transform .2s ease, box-shadow .2s ease }
```
并把根 `<n-card size="small" hoverable>` 加 `class="card"`，在 scoped 中加：
```css
.card { transition: transform .2s ease, box-shadow .2s ease }
.card:hover { transform: translateY(-2px) }
.actions :deep(.n-button) { color: inherit }
```

- [ ] **Step 3: 跑测试确认不回归**

Run: `cd /i/trae/wd14/wd14-tagger-web/frontend && npx vitest run src/__tests__/ImageCard.test.ts`
Expected: PASS（5 tests）

- [ ] **Step 4: build**

Run: `cd /i/trae/wd14/wd14-tagger-web/frontend && npm run build`
Expected: exit 0

- [ ] **Step 5: 提交**

```bash
git -C /i/trae/wd14/wd14-tagger-web add frontend/src/components/ImageCard.vue
git -C /i/trae/wd14/wd14-tagger-web commit -m "feat(ui): ImageCard emoji→SVG 图标 + hover 上浮"
```

---

### Task 6: GalleryPage 筛选栏面板化

**Files:**
- Modify: `frontend/src/views/GalleryPage.vue`
- Test: `frontend/src/__tests__/GalleryPage.test.ts`（新建）

- [ ] **Step 1: 写失败测试**

`frontend/src/__tests__/GalleryPage.test.ts`:
```ts
import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import GalleryPage from '../views/GalleryPage.vue'

vi.mock('naive-ui', async () => {
  const actual: any = await vi.importActual('naive-ui')
  return { ...actual, useMessage: () => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn() }) }
})

describe('GalleryPage', () => {
  it('渲染筛选面板与三个筛选标签', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ items: [], total: 0 }) }) as any))
    const w = mount(GalleryPage, { global: { stubs: { NImage: true } } })
    await flushPromises()
    expect(w.find('.filter-bar').exists()).toBe(true)
    const labels = w.find('.filter-bar').text()
    expect(labels).toContain('日期')
    expect(labels).toContain('标签')
    expect(labels).toContain('提示词')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /i/trae/wd14/wd14-tagger-web/frontend && npx vitest run src/__tests__/GalleryPage.test.ts`
Expected: FAIL — `.filter-bar` 找不到

- [ ] **Step 3: 改 GalleryPage.vue 模板顶部筛选区**

把当前模板开头的筛选 `<div style="margin-bottom:12px;...">…</div>` 整段替换为：
```html
  <n-card size="small" class="filter-bar" style="margin-bottom:16px">
    <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">
      <div class="field"><span class="field-label">日期</span>
        <n-date-picker v-model:value="dateTs" type="date" clearable size="small"
                       @update:value="onDate" style="width:160px" /></div>
      <div class="field"><span class="field-label">标签</span>
        <n-select v-model:value="selTags" multiple clearable filterable size="small"
                  :options="tagOptions" placeholder="多选标签（交集筛选）"
                  @update:value="onTags" style="min-width:240px;max-width:360px" /></div>
      <div class="field"><span class="field-label">提示词</span>
        <n-input :value="promptText" placeholder="提示词（逗号或空格分隔，交集）" size="small" clearable
                 @update:value="onPrompt" @keyup.enter="onPromptEnter"
                 style="min-width:240px;max-width:320px" /></div>
    </div>
  </n-card>
```
并在 `<template>` 末尾后、`</template>` 内无需额外样式块，改在文件追加 `<style scoped>`：
```vue
<style scoped>
.field { display: flex; align-items: center; gap: 8px }
.field-label { font-size: 13px; font-weight: 600; color: var(--n-text-color-3, #6b7280); min-width: 28px }
</style>
```
（若 GalleryPage.vue 已有 `<style scoped>`，则把以上规则并入已有块。）

- [ ] **Step 4: 跑测试确认通过**

Run: `cd /i/trae/wd14/wd14-tagger-web/frontend && npx vitest run src/__tests__/GalleryPage.test.ts`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git -C /i/trae/wd14/wd14-tagger-web add frontend/src/views/GalleryPage.vue frontend/src/__tests__/GalleryPage.test.ts
git -C /i/trae/wd14/wd14-tagger-web commit -m "feat(ui): GalleryPage 筛选栏面板化 + 标签化"
```

---

### Task 7: 详情页图片区深底容器

**Files:**
- Modify: `frontend/src/views/DetailPage.vue`
- Modify: `frontend/src/views/PromptboxDetailPage.vue`

**Interfaces:**
- 说明：详情页布局（左右栅格）不变，仅给图片外层加统一深底容器 `.img-wrap` 衬出图片。既有 `PromptboxDetailPage.test.ts` 不受影响（断言不涉及该 class）。

- [ ] **Step 1: 跑现有详情页测试建立基线**

Run: `cd /i/trae/wd14/wd14-tagger-web/frontend && npx vitest run src/__tests__/PromptboxDetailPage.test.ts`
Expected: PASS（5 tests）

- [ ] **Step 2: DetailPage.vue 给 n-image 包裹**

找到 `<n-image :src="fileUrl(id, meta.image.thumb)" ... />`，用 `<div class="img-wrap">` 包裹：
```html
        <div class="img-wrap">
          <n-image :src="fileUrl(id, meta.image.thumb)" :preview-src="fileUrl(id, meta.image.original)"
                   object-fit="contain" style="max-height:420px;width:100%;display:block" />
        </div>
```
在 DetailPage.vue 的 `<style scoped>` 追加：
```css
.img-wrap {
  background: #0f1115; border-radius: 10px; padding: 8px;
  display: flex; align-items: center; justify-content: center;
}
```

- [ ] **Step 3: PromptboxDetailPage.vue 同样包裹**

找到 `<n-image v-if="hasImage" ... />` 与无图占位 `<div v-else class="no-img">…</div>`，整体用 `<div class="img-wrap">` 包裹：
```html
        <div class="img-wrap">
          <n-image v-if="hasImage" :src="promptboxImageUrl(id, item.image_names[0])"
                   :preview-src="promptboxImageUrl(id, item.image_names[0])"
                   object-fit="contain" style="max-height:420px;width:100%;display:block" />
          <div v-else class="no-img">无图片（点下方「上传图片」或「重新反推」）</div>
        </div>
```
在 PromptboxDetailPage.vue 的 `<style scoped>` 追加同样的 `.img-wrap` 规则（与 DetailPage 一致）。

- [ ] **Step 4: 跑测试确认不回归**

Run: `cd /i/trae/wd14/wd14-tagger-web/frontend && npx vitest run src/__tests__/PromptboxDetailPage.test.ts`
Expected: PASS（5 tests）

- [ ] **Step 5: build**

Run: `cd /i/trae/wd14/wd14-tagger-web/frontend && npm run build`
Expected: exit 0

- [ ] **Step 6: 提交**

```bash
git -C /i/trae/wd14/wd14-tagger-web add frontend/src/views/DetailPage.vue frontend/src/views/PromptboxDetailPage.vue
git -C /i/trae/wd14/wd14-tagger-web commit -m "feat(ui): 详情页图片区加深底容器 img-wrap"
```

---

### Task 8: 全站统一收尾 + 全量回归

**Files:**
- Modify: `frontend/src/components/BatchBadge.vue`（emoji→SVG）
- 其余页面（Upload/Random/Settings/CollectionList/PromptBox/BatchDetail/TagEditor/BatchBars）：套用全局主题即自动适配，仅检查无残留 emoji 文字图标。

- [ ] **Step 1: BatchBadge emoji→SVG**

`frontend/src/components/BatchBadge.vue`：现状 19-20 行用文字符号 `✓`/`↑`/`↓`，替换为 SVG 图标。

(a) `<script setup>` 的导入改为（加 `NIcon` 与三个图标）：
```ts
import { NTag, NIcon } from 'naive-ui'
import { IconCheck, IconUpload as IconUp, IconDownload as IconDl } from './icons'
```

(b) `<template>` 的 `<n-tag>` 整段替换为（三个文字符号 → 图标）：
```html
  <n-tag v-if="visible()" data-testid="badge"
         :type="state.phase === 'done' ? 'success' : 'info'" size="small"
         :style="{ cursor: state.batchId ? 'pointer' : 'default' }" @click="toDetail">
    <template v-if="state.phase === 'done'"><n-icon :component="IconCheck" /> 完成 {{ state.total }}</template>
    <template v-else><n-icon :component="IconUp" /> {{ state.uploaded }}/{{ state.total }} · <n-icon :component="IconDl" /> {{ state.tagged }}/{{ state.total }}</template>
  </n-tag>
```
（`IconCheck/IconUp/IconDl` 均已在 Task 3 定义；`NIcon` 已在上方导入行引入。）

- [ ] **Step 2: 全量前端测试**

Run: `cd /i/trae/wd14/wd14-tagger-web/frontend && npx vitest run`
Expected: 全部 PASS（含新增 theme/useTheme/icons/GalleryPage 测试）

- [ ] **Step 3: vue-tsc + build**

Run: `cd /i/trae/wd14/wd14-tagger-web/frontend && npx vue-tsc -b && npm run build`
Expected: exit 0

- [ ] **Step 4: 人工核验清单**

启动 `cd /i/trae/wd14/wd14-tagger-web && start.bat`，浏览器核对：
- [ ] 侧栏 6 菜单项带图标、当前页高亮；窄屏可折叠。
- [ ] 侧栏底主题钮：点击在 自动/浅色/深色 间循环，刷新后保持。
- [ ] 图库卡片 hover 上浮、复制/下载是 SVG 图标。
- [ ] 图库筛选栏为面板；详情页图片区深底；深/浅两套色均正常。
- [ ] 无残留 emoji 图标。

- [ ] **Step 5: 提交收尾**

```bash
git -C /i/trae/wd14/wd14-tagger-web add -A
git -C /i/trae/wd14/wd14-tagger-web commit -m "feat(ui): BatchBadge emoji→SVG + 全站收尾"
```

- [ ] **Step 6: 合并 master（可选，待用户确认）**

```bash
git -C /i/trae/wd14/wd14-tagger-web checkout master
git -C /i/trae/wd14/wd14-tagger-web merge --ff-only feat/ui-premium-redesign
```

---

## Self-Review（已完成）

**Spec coverage**：spec 的 6 节均有任务覆盖 — 主题系统(Task 1+2+4)、布局骨架(Task 4)、组件改造(Task 5+6+7+8)、图标(Task 3+8)、排版动效(Task 4 的 global.css + 过渡)、范围全站(Task 4-8)。
**Placeholder**：无 TBD/TODO；每个代码 step 含完整代码。
**Type consistency**：`useTheme()` 返回 `{ mode, effective, setMode }` 在 Task 2 定义、Task 4 消费一致；`lightOverrides/darkOverrides`、图标导出名跨任务一致；`IconCheck` 已在 Task 3 定义，供 Task 8 BatchBadge 使用（无悬空引用）。
**现状对齐**：Task 6 的 `dateTs/selTags/promptText/onDate/onTags/onPrompt` 与 GalleryPage.vue 当前 11-59 行一致；Task 7 的 `hasImage/promptboxImageUrl/item.image_names[0]` 与 PromptboxDetailPage.vue 195-198 行、DetailPage.vue 117 行一致；Task 8 的 `state.phase/total/uploaded/tagged/batchId` 与 BatchBadge.vue 现状一致。
