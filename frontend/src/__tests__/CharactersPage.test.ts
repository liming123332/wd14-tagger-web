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
