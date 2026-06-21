import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import CharacterDetailPage from '../views/CharacterDetailPage.vue'

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
  entry_key: 'char:danbooru:1', source: 'danbooru', name: 'miku', series: 'vocaloid',
  trigger: 'miku', core_tags: 'miku, 1girl',
  thumb_url: '/api/cf/asset?kind=char&source=danbooru&key=1&which=thumb',
  image_url: '/api/cf/asset?kind=char&source=danbooru&key=1&which=image',
  favorite: false, locked_tags: ['miku', '1girl'],
  categories: { head: { tags: ['long hair'], phrase: 'long hair', user_edited: false } },
  extras: { tags: [], phrase: '', user_edited: false },
  custom_tags: [], model: 'wd14', gen_threshold: 0.35, char_threshold: 0.9, image_override: null,
}

describe('CharacterDetailPage', () => {
  beforeEach(() => vi.unstubAllGlobals())

  function stubFetch(handler: (url: string, opts?: any) => any) {
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts?: any) => {
      return { ok: true, json: async () => handler(url, opts) } as any
    }))
  }

  it('加载详情：渲染锁定标签 + 分类标签', async () => {
    stubFetch((url) => { if (url.includes('/api/cf/character?')) return DETAIL; return {} })
    const w = mount(CharacterDetailPage, { global: { stubs: { NImage: true, NUpload: true } } })
    await flushPromises()
    const locked = w.findAll('.locked-tag').map(t => t.text())
    expect(locked).toContain('🔒 miku')
    expect(locked).toContain('🔒 1girl')
    expect(w.text()).toContain('long hair')
  })

  it('save 的 PUT body 含 categories/extras/custom_tags，不含 locked_tags', async () => {
    const seen: any[] = []
    stubFetch((url, opts) => {
      if (url.includes('/api/cf/character?') && opts && opts.method === 'PUT') seen.push(opts.body)
      if (url.includes('/api/cf/character?')) return DETAIL
      return {}
    })
    const w = mount(CharacterDetailPage, { global: { stubs: { NImage: true, NUpload: true } } })
    await flushPromises()
    await (w.vm as any).save()
    await flushPromises()
    expect(seen.length).toBe(1)
    const body = JSON.parse(seen[0])
    expect(body.categories).toBeTruthy()
    expect(body.custom_tags).toEqual([])
    expect(body.locked_tags).toBeUndefined()
  })

  it('反推调 /api/cf/character/tag', async () => {
    const urls: string[] = []
    stubFetch((url) => {
      if (url.includes('/api/cf/character/tag')) { urls.push(url); return DETAIL }
      if (url.includes('/api/cf/character?')) return DETAIL
      return {}
    })
    const w = mount(CharacterDetailPage, { global: { stubs: { NImage: true, NUpload: true } } })
    await flushPromises()
    await (w.vm as any).reTag()
    await flushPromises()
    expect(urls.some(u => u.includes('/api/cf/character/tag?source=danbooru&key=1'))).toBe(true)
  })

  it('换图 POST FormData 到 /api/cf/character/image', async () => {
    const seen: any[] = []
    stubFetch((url, opts) => {
      if (url.includes('/api/cf/character/image')) { seen.push({ url, body: opts?.body }); return { image_override: 'new.png' } }
      if (url.includes('/api/cf/character?')) return DETAIL
      return {}
    })
    const w = mount(CharacterDetailPage, { global: { stubs: { NImage: true, NUpload: true } } })
    await flushPromises()
    await (w.vm as any).uploadImage(new File(['x'], 'up.png', { type: 'image/png' }))
    await flushPromises()
    expect(seen[0].url).toContain('/api/cf/character/image?source=danbooru&key=1')
    expect(seen[0].body).toBeInstanceOf(FormData)
  })

  it('收藏 toggle 调 /api/cf/character/favorite', async () => {
    const urls: string[] = []
    stubFetch((url) => {
      if (url.includes('/api/cf/character/favorite')) { urls.push(url); return { favorite: true } }
      if (url.includes('/api/cf/character?')) return DETAIL
      return {}
    })
    const w = mount(CharacterDetailPage, { global: { stubs: { NImage: true, NUpload: true } } })
    await flushPromises()
    await (w.vm as any).toggleFav()
    await flushPromises()
    expect(urls.some(u => u.includes('/api/cf/character/favorite?source=danbooru&key=1'))).toBe(true)
  })
})
