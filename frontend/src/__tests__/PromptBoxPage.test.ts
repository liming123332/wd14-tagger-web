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
})
