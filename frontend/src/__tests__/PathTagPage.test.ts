import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('naive-ui', async () => {
  const actual: any = await vi.importActual('naive-ui')
  return { ...actual, useMessage: () => ({ warning: vi.fn(), success: vi.fn(), error: vi.fn() }) }
})

// vi.hoisted：保证 mock 工厂能引用这些状态/mock（工厂被提升到模块顶部执行）
const { taggerState, pathState, startMock, resetMock } = vi.hoisted(() => ({
  taggerState: {
    selected: 'cl_tagger_v2',
    taggers: [{ key: 'cl_tagger_v2', label: 'CL Tagger v2', downloaded: true }],
    downloading: null,
    unloading: false,
  },
  pathState: {
    phase: 'idle', total: 0, done: 0, ok: 0, skipped: 0, failed: 0,
    current: '', jobId: null, errors: [] as any[],
  },
  startMock: vi.fn(async () => {}),
  resetMock: vi.fn(),
}))

vi.mock('../composables/useTagger', () => ({
  useTagger: () => ({
    state: taggerState,
    setSelected: vi.fn((k: string) => { taggerState.selected = k }),
    refresh: vi.fn(async () => {}),
    isDownloaded: (k: string) => taggerState.taggers.some((t: any) => t.key === k && t.downloaded),
    download: vi.fn(async () => {}),
    unloadAll: vi.fn(async () => {}),
  }),
}))
vi.mock('../composables/usePathTag', () => ({
  usePathTag: () => ({
    state: pathState,
    isBusy: () => pathState.phase === 'running',
    start: startMock,
    reset: resetMock,
  }),
}))

import PathTagPage from '../views/PathTagPage.vue'

describe('PathTagPage', () => {
  beforeEach(() => {
    pathState.phase = 'idle'
    pathState.errors = []
    taggerState.selected = 'cl_tagger_v2'
    taggerState.taggers = [{ key: 'cl_tagger_v2', label: 'CL Tagger v2', downloaded: true }]
    startMock.mockClear()
    resetMock.mockClear()
  })

  it('渲染路径输入与开始按钮', () => {
    const w = mount(PathTagPage, { global: { stubs: { NMenu: true } } })
    expect(w.find('[data-testid="start-btn"]').exists()).toBe(true)
    expect(w.text()).toContain('文件夹路径')
  })

  it('初始（idle + 已下载）开始按钮可点', () => {
    const w = mount(PathTagPage, { global: { stubs: { NMenu: true } } })
    expect((w.find('[data-testid="start-btn"]').element as HTMLButtonElement).disabled).toBe(false)
  })

  it('处理中（running）开始按钮禁用', () => {
    // mount 前置 phase=running（pathState 非 reactive，mount 时一次性求值 isBusy 即可）
    pathState.phase = 'running'
    const w = mount(PathTagPage, { global: { stubs: { NMenu: true } } })
    expect((w.find('[data-testid="start-btn"]').element as HTMLButtonElement).disabled).toBe(true)
  })

  it('所选模型未下载时开始按钮禁用', async () => {
    taggerState.taggers = [{ key: 'cl_tagger_v2', label: 'CL Tagger v2', downloaded: false }]
    const w = mount(PathTagPage, { global: { stubs: { NMenu: true } } })
    await w.vm.$nextTick()
    expect((w.find('[data-testid="start-btn"]').element as HTMLButtonElement).disabled).toBe(true)
  })
})
