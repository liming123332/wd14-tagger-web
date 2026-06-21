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
