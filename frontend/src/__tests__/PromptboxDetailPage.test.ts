import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import PromptboxDetailPage from '../views/PromptboxDetailPage.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'c1' } }),
  useRouter: () => ({ push: vi.fn() }),
}))
vi.mock('naive-ui', async () => {
  const actual: any = await vi.importActual('naive-ui')
  return { ...actual, useMessage: () => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn() }) }
})
vi.mock('../composables/useTagger', () => {
  const state = {
    selected: 'wd14',
    taggers: [{ key: 'wd14', label: 'WD14', downloaded: true }],
    downloading: null,
  }
  return {
    useTagger: () => ({
      state,
      setSelected: vi.fn(),
      refresh: vi.fn(async () => {}),
      isDownloaded: () => true,
      download: vi.fn(async () => {}),
    }),
  }
})

const ITEM = {
  id: 'c1', title: '测试收藏', raw_prompt: 'long hair, dress',
  categories: { head: ['long hair'], clothing: ['dress'] },
  extras: ['weird'], image_names: ['img1.png'],
  created_at: '', updated_at: '',
  model: 'wd14', gen_threshold: 0.35, char_threshold: 0.9,
  raw_tags: { 'long hair': 0.9 },
}

describe('PromptboxDetailPage', () => {
  beforeEach(() => { vi.unstubAllGlobals() })

  it('加载收藏并把 string[] categories 渲染为标签', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url === '/api/promptbox/c1') return { ok: true, json: async () => ITEM } as any
      return { ok: true, json: async () => ({}) } as any
    }))
    const w = mount(PromptboxDetailPage, { global: { stubs: { NImage: true, NUpload: true } } })
    await flushPromises()
    // title 在 NInput 的 value（不在 textContent），单独查 input
    expect(w.findAll('input').some(i => (i.element as HTMLInputElement).value === '测试收藏')).toBe(true)
    // 标签在 NTag textContent
    expect(w.text()).toContain('long hair')
    expect(w.text()).toContain('dress')
  })

  it('save 把 categories 回写为 string[]（6 类全量）', async () => {
    const seen: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts?: any) => {
      if (url === '/api/promptbox/c1' && opts && opts.method === 'PUT') {
        seen.push(opts.body)
        return { ok: true, json: async () => ITEM } as any
      }
      if (url === '/api/promptbox/c1') return { ok: true, json: async () => ITEM } as any
      return { ok: true, json: async () => ({}) } as any
    }))
    const w = mount(PromptboxDetailPage, { global: { stubs: { NImage: true, NUpload: true } } })
    await flushPromises()
    await (w.vm as any).save()
    await flushPromises()
    expect(seen.length).toBe(1)
    expect(seen[0].get('categories')).toBe(JSON.stringify({
      quality: [], head: ['long hair'], clothing: ['dress'],
      view: [], action: [], scene: [],
    }))
  })

  it('无图时「重新反推」按钮 disabled', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url === '/api/promptbox/c1') return { ok: true, json: async () => ({ ...ITEM, image_names: [] }) } as any
      return { ok: true, json: async () => ({}) } as any
    }))
    const w = mount(PromptboxDetailPage, { global: { stubs: { NImage: true, NUpload: true } } })
    await flushPromises()
    const reTagBtn = w.findAll('button').find(b => b.text().includes('重新反推'))
    expect(reTagBtn).toBeTruthy()
    expect((reTagBtn!.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('reclassify 把手改类作为 keep 传给后端', async () => {
    const seen: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts?: any) => {
      if (url === '/api/promptbox/c1/reclassify') {
        seen.push(JSON.parse(opts.body))
        return { ok: true, json: async () => ITEM } as any
      }
      if (url === '/api/promptbox/c1') return { ok: true, json: async () => ITEM } as any
      return { ok: true, json: async () => ({}) } as any
    }))
    const w = mount(PromptboxDetailPage, { global: { stubs: { NImage: true, NUpload: true } } })
    await flushPromises()
    // 模拟手改 head 类
    ;(w.vm as any).setCat('head', { tags: ['my tag'], phrase: 'my tag', user_edited: true })
    await (w.vm as any).reClassify()
    await flushPromises()
    expect(seen[0].keep).toEqual({ head: ['my tag'] })
  })

  it('上传图片：update PUT 带 files，不触发 /tag（不自动反推）', async () => {
    const puts: any[] = []
    let tagged = false
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts?: any) => {
      if (url === '/api/promptbox/c1' && opts && opts.method === 'PUT') {
        puts.push(opts.body)
        return { ok: true, json: async () => ({ ...ITEM, image_names: ['new.png'] }) } as any
      }
      if (url === '/api/promptbox/c1/tag') { tagged = true; return { ok: true, json: async () => ITEM } as any }
      if (url === '/api/promptbox/c1') return { ok: true, json: async () => ITEM } as any
      return { ok: true, json: async () => ({}) } as any
    }))
    const w = mount(PromptboxDetailPage, { global: { stubs: { NImage: true, NUpload: true } } })
    await flushPromises()
    await (w.vm as any).uploadImage(new File(['x'], 'up.png', { type: 'image/png' }))
    await flushPromises()
    expect(puts.length).toBe(1)
    expect(puts[0].get('files')).toBeTruthy()
    expect(tagged).toBe(false)
  })

  it('加载 v2 收藏时阈值刷成 0.55（即便 meta 记的是旧值 0.35/0.9）', async () => {
    const item_v2 = { ...ITEM, model: 'cl_tagger_v2', gen_threshold: 0.35, char_threshold: 0.9 }
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url === '/api/promptbox/c1') return { ok: true, json: async () => item_v2 } as any
      return { ok: true, json: async () => ({}) } as any
    }))
    const w = mount(PromptboxDetailPage, { global: { stubs: { NImage: true, NUpload: true } } })
    await flushPromises()
    // NInputNumber 渲染为 input：v2 强制 0.55/0.55，meta 记的旧值不应出现
    const vals = w.findAll('input').map(i => (i.element as HTMLInputElement).value)
    expect(vals.filter(v => v === '0.55').length).toBeGreaterThanOrEqual(2)
    expect(vals.filter(v => v === '0.35' || v === '0.9').length).toBe(0)
  })
})
