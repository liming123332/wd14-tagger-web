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

// Task 5：列表页顶部「最近查看」横向滚动区。
// listCfRecent 走 fetch('/api/cf/recent?kind=&limit=')，故沿用现有 vi.stubGlobal('fetch') mock 模式，
// 在 fetch stub 内按 URL 分支返回不同数据。
describe('CharactersPage 最近查看区', () => {
  beforeEach(() => vi.unstubAllGlobals())

  it('recent 非空时渲染 .recent-bar 且含卡片名称', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url.includes('/api/cf/recent')) return {
        ok: true,
        json: async () => ({ items: [{ entry_key: 'char:danbooru:r1', source: 'danbooru', name: 'Recent One', core_tags: '1girl', favorite: false, thumb_url: '' }] }),
      } as any
      if (url.includes('/characters/series')) return { ok: true, json: async () => [] } as any
      return { ok: true, json: async () => ({ items: [], total: 0 }) } as any
    }))
    const w = mount(CharactersPage, { global: { stubs: { NImage: true } } })
    await flushPromises()
    expect(w.find('.recent-bar').exists()).toBe(true)
    expect(w.text()).toContain('Recent One')
  })

  it('recent 为空时 .recent-bar 不存在', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url.includes('/api/cf/recent')) return { ok: true, json: async () => ({ items: [] }) } as any
      if (url.includes('/characters/series')) return { ok: true, json: async () => [] } as any
      return { ok: true, json: async () => ({ items: [], total: 0 }) } as any
    }))
    const w = mount(CharactersPage, { global: { stubs: { NImage: true } } })
    await flushPromises()
    expect(w.find('.recent-bar').exists()).toBe(false)
  })
})
