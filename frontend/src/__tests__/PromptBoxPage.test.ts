import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import PromptBoxPage from '../views/PromptBoxPage.vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('naive-ui', async () => {
  const actual: any = await vi.importActual('naive-ui')
  return { ...actual, useMessage: () => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn() }) }
})

describe('PromptBoxPage', () => {
  beforeEach(() => { vi.unstubAllGlobals() })

  it('onMounted 拉取收藏列表并渲染卡片', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url === '/api/promptbox') {
        return { ok: true, json: async () => [{ id: 'p1', title: '我的收藏', raw_prompt: 'long hair', categories: {}, extras: [], image_names: [], created_at: '', updated_at: '' }] } as any
      }
      return { ok: true, json: async () => ({}) } as any
    }))
    const w = mount(PromptBoxPage, { global: { stubs: { NMenu: true } } })
    await flushPromises()
    expect(w.text()).toContain('我的收藏')
  })

  it('点拆分按逗号文本调用 split 并显示分栏', async () => {
    const calls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, _opts: any) => {
      calls.push(url)
      if (url === '/api/promptbox/split') {
        return { ok: true, json: async () => ({ categories: { head: ['long hair'], clothing: ['dress'] }, extras: ['weird'] }) } as any
      }
      return { ok: true, json: async () => [] } as any
    }))
    const w = mount(PromptBoxPage, { global: { stubs: { NMenu: true } } })
    await flushPromises()
    // 找到 textarea 并填入文本
    const ta = w.find('textarea')
    await ta.setValue('long hair, dress, weird')
    // 点拆分按钮
    const splitBtn = w.findAll('button').find(b => b.text().includes('拆分'))
    expect(splitBtn).toBeTruthy()
    await splitBtn!.trigger('click')
    await flushPromises()
    expect(calls).toContain('/api/promptbox/split')
    expect(w.text()).toContain('long hair')
    expect(w.text()).toContain('dress')
  })

  it('列表卡片渲染且含删除按钮', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url === '/api/promptbox') {
        return { ok: true, json: async () => [{ id: 'p1', title: '待删', raw_prompt: 'x', categories: {}, extras: [], image_names: [], created_at: '', updated_at: '' }] } as any
      }
      return { ok: true, json: async () => ({}) } as any
    }))
    const w = mount(PromptBoxPage, { global: { stubs: { NMenu: true } } })
    await flushPromises()
    expect(w.text()).toContain('待删')
    const delBtn = w.findAll('button').find(b => b.text().includes('删除'))
    expect(delBtn).toBeTruthy()
    // 注：n-popconfirm 单击只弹确认层，DELETE 调用由 Task 3 test_delete 在 API 层覆盖；
    // 此处只验证删除按钮存在，避免依赖 popconfirm 弹层 DOM 的 flaky。
  })
})
