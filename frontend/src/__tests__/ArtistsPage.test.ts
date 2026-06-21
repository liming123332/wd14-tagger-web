import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { h, defineComponent } from 'vue'
import ArtistsPage from '../views/ArtistsPage.vue'

// NGrid/NGridItem 在 jsdom 下因 ResizeObserver 触发渲染崩溃；用透传 slot 的占位组件替代
const SlotStub = (tag: string) => defineComponent({
  name: tag,
  setup(_, { slots }) { return () => h(tag, slots.default ? slots.default() : []) },
})

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
    const w = mount(ArtistsPage, { global: { stubs: { NImage: true, NGrid: SlotStub('div'), NGridItem: SlotStub('div') } } })
    await flushPromises()
    expect(w.text()).toContain('ebifurya')
    expect(w.html()).toContain('which=1')
  })

  it('点击卡片跳转艺术家详情', async () => {
    stubFetch()
    const w = mount(ArtistsPage, { global: { stubs: { NImage: true, NGrid: SlotStub('div'), NGridItem: SlotStub('div') } } })
    await flushPromises()
    await w.find('.thumb').trigger('click')
    expect(push).toHaveBeenCalledWith('/artists/danbooru/1')
  })

  it('收藏 toggle 调 /api/cf/artist/favorite', async () => {
    const calls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url.includes('/api/cf/artist/favorite')) calls.push(url)
      if (url.includes('/api/cf/artists')) return { ok: true, json: async () => ({ items: [ITEM], total: 1 }) } as any
      return { ok: true, json: async () => ({ favorite: true }) } as any
    }))
    const w = mount(ArtistsPage, { global: { stubs: { NImage: true, NGrid: SlotStub('div'), NGridItem: SlotStub('div') } } })
    await flushPromises()
    const fav = w.findAll('button').find(b => b.attributes('title') === '收藏')!
    await fav.trigger('click')
    await flushPromises()
    expect(calls.some(u => u.includes('/api/cf/artist/favorite?source=danbooru&key=1'))).toBe(true)
  })
})

// Task 5：列表页顶部「最近查看」横向滚动区。
// listCfRecent 走 fetch('/api/cf/recent?kind=&limit=')，故沿用现有 vi.stubGlobal('fetch') mock 模式。
describe('ArtistsPage 最近查看区', () => {
  beforeEach(() => { vi.unstubAllGlobals(); push.mockClear() })

  it('recent 非空时渲染 .recent-bar 且含卡片名称', async () => {
    const recentItem = { entry_key: 'artist:danbooru:r1', source: 'danbooru', name: 'Recent Artist', tag: 'recent_artist', favorite: false }
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url.includes('/api/cf/recent')) return { ok: true, json: async () => ({ items: [recentItem] }) } as any
      if (url.includes('/api/cf/artists')) return { ok: true, json: async () => ({ items: [], total: 0 }) } as any
      return { ok: true, json: async () => ({ items: [], total: 0 }) } as any
    }))
    const w = mount(ArtistsPage, { global: { stubs: { NImage: true, NGrid: SlotStub('div'), NGridItem: SlotStub('div') } } })
    await flushPromises()
    expect(w.find('.recent-bar').exists()).toBe(true)
    expect(w.text()).toContain('Recent Artist')
  })

  it('recent 为空时 .recent-bar 不存在', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url.includes('/api/cf/recent')) return { ok: true, json: async () => ({ items: [] }) } as any
      if (url.includes('/api/cf/artists')) return { ok: true, json: async () => ({ items: [], total: 0 }) } as any
      return { ok: true, json: async () => ({ items: [], total: 0 }) } as any
    }))
    const w = mount(ArtistsPage, { global: { stubs: { NImage: true, NGrid: SlotStub('div'), NGridItem: SlotStub('div') } } })
    await flushPromises()
    expect(w.find('.recent-bar').exists()).toBe(false)
  })
})
