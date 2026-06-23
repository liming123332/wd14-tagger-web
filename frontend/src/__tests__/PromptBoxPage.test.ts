import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import PromptBoxPage from '../views/PromptBoxPage.vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('naive-ui', async () => {
  const actual: any = await vi.importActual('naive-ui')
  return { ...actual, useMessage: () => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn() }) }
})
// mock useTagger：避免 onMounted refresh 触发真 fetch，state.taggers 保持为数组
vi.mock('../composables/useTagger', () => {
  const state = {
    selected: 'wd14',
    taggers: [{ key: 'wd14', label: 'WD14', downloaded: true }],
    downloading: null,
  }
  return {
    useTagger: () => ({
      state,
      setSelected: vi.fn((k: string) => { state.selected = k }),
      refresh: vi.fn(async () => {}),
      isDownloaded: (k: string) => state.taggers.some((t: any) => t.key === k && t.downloaded),
      download: vi.fn(async () => {}),
    }),
  }
})

describe('PromptBoxPage 工作台', () => {
  beforeEach(() => { vi.unstubAllGlobals() })

  it('含上传反推按钮', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ items: [] }) }) as any))
    const w = mount(PromptBoxPage, { global: { stubs: { NMenu: true } } })
    await flushPromises()
    expect(w.findAll('button').find(b => b.text().includes('反推'))).toBeTruthy()
  })

  it('粘贴提示词拆分并显示分类', async () => {
    const calls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, _opts: any) => {
      calls.push(url)
      if (url === '/api/promptbox/split') {
        return { ok: true, json: async () => ({ categories: { head: ['long hair'], clothing: ['dress'] }, extras: ['weird'] }) } as any
      }
      return { ok: true, json: async () => ({ items: [] }) } as any
    }))
    const w = mount(PromptBoxPage, { global: { stubs: { NMenu: true } } })
    await flushPromises()
    const ta = w.find('textarea')
    await ta.setValue('long hair, dress, weird')
    const splitBtn = w.findAll('button').find(b => b.text().includes('粘贴拆分'))
    expect(splitBtn).toBeTruthy()
    await splitBtn!.trigger('click')
    await flushPromises()
    expect(calls).toContain('/api/promptbox/split')
    // 工作区出现粘贴项 + 拆分编辑区显示标签
    expect(w.text()).toContain('工作区')
    expect(w.text()).toContain('long hair')
    expect(w.text()).toContain('dress')
  })

  it('上传反推后另存为收藏携带 raw_tags/model', async () => {
    const seen: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts: any) => {
      if (url === '/api/promptbox/analyze') {
        return { ok: true, json: async () => ({ items: [{
          local_id: 'ws1', original: 'original.png', thumb: 'thumb.webp',
          width: 100, height: 100, model: 'wd3',
          categories: { head: ['long hair'] }, extras: ['weird'],
          raw_prompt: 'long hair, weird',
          raw_tags: { 'long hair': 0.9, 'weird': 0.4 },
        }] }) } as any
      }
      if (url === '/api/promptbox' && opts && opts.method === 'POST') {
        seen.push(opts.body)
        return { ok: true, json: async () => ({ id: 'new1' }) } as any
      }
      // workspace 原图（workspaceToFile fetch blob）
      return { ok: true, json: async () => ({}), blob: async () => new Blob([new Uint8Array([1])], { type: 'image/png' }) } as any
    }))
    const w = mount(PromptBoxPage, { global: { stubs: { NMenu: true } } })
    await flushPromises()
    await (w.vm as any).doAnalyze([new File(['x'], 'a.png')])
    await flushPromises()
    await (w.vm as any).saveAsCollection()
    await flushPromises()
    expect(seen.length).toBe(1)
    expect(seen[0].get('raw_tags')).toBe(JSON.stringify({ 'long hair': 0.9, 'weird': 0.4 }))
    expect(seen[0].get('model')).toBe('wd3')
  })

  it('粘贴+附图：调 workspace/image + split，产带图项', async () => {
    const calls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      calls.push(url)
      if (url === '/api/promptbox/workspace/image') {
        return { ok: true, json: async () => ({ items: [{
          local_id: 'ws9', original: 'original.png', thumb: 'thumb.webp', width: 10, height: 10,
        }] }) } as any
      }
      if (url === '/api/promptbox/split') {
        return { ok: true, json: async () => ({ categories: { head: ['long hair'] }, extras: [] }) } as any
      }
      return { ok: true, json: async () => ({ items: [] }) } as any
    }))
    const w = mount(PromptBoxPage, { global: { stubs: { NMenu: true } } })
    await flushPromises()
    ;(w.vm as any).pasteTextImg = 'long hair'
    ;(w.vm as any).pasteFile = new File(['x'], 'a.png')
    await (w.vm as any).doPasteSplitWithImage()
    await flushPromises()
    expect(calls).toContain('/api/promptbox/workspace/image')
    expect(calls).toContain('/api/promptbox/split')
    // 新建带图项被选中 → 拆分编辑区显示其分类标签
    expect(w.text()).toContain('long hair')
  })

  it('粘贴不附图：仅 split，不调 workspace/image', async () => {
    const calls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      calls.push(url)
      if (url === '/api/promptbox/split') {
        return { ok: true, json: async () => ({ categories: { head: ['cat'] }, extras: [] }) } as any
      }
      return { ok: true, json: async () => ({ items: [] }) } as any
    }))
    const w = mount(PromptBoxPage, { global: { stubs: { NMenu: true } } })
    await flushPromises()
    ;(w.vm as any).pasteTextImg = 'cat'
    ;(w.vm as any).pasteFile = null
    await (w.vm as any).doPasteSplitWithImage()
    await flushPromises()
    expect(calls).toContain('/api/promptbox/split')
    expect(calls.some(u => u === '/api/promptbox/workspace/image')).toBe(false)
    expect(w.text()).toContain('cat')
  })
})
