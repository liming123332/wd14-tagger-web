import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import CollectionListPage from '../views/CollectionListPage.vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('naive-ui', async () => {
  const actual: any = await vi.importActual('naive-ui')
  return { ...actual, useMessage: () => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn() }) }
})

describe('CollectionListPage', () => {
  beforeEach(() => { vi.unstubAllGlobals() })

  it('onMounted 拉取收藏并渲染卡片', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url === '/api/promptbox') {
        return { ok: true, json: async () => [{ id: 'c1', title: '我的收藏', raw_prompt: 'long hair', categories: { head: ['long hair'] }, extras: [], image_names: [], created_at: '', updated_at: '' }] } as any
      }
      return { ok: true, json: async () => ({}) } as any
    }))
    const w = mount(CollectionListPage, { global: { stubs: { NMenu: true } } })
    await flushPromises()
    expect(w.text()).toContain('我的收藏')
  })

  it('关键词子串过滤收藏', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url === '/api/promptbox') {
        return { ok: true, json: async () => [
          { id: 'c1', title: '猫耳少女', raw_prompt: 'cat ears', categories: {}, extras: [], image_names: [], created_at: '', updated_at: '' },
          { id: 'c2', title: '修狗', raw_prompt: 'dog', categories: {}, extras: [], image_names: [], created_at: '', updated_at: '' },
        ] } as any
      }
      return { ok: true, json: async () => ({}) } as any
    }))
    const w = mount(CollectionListPage, { global: { stubs: { NMenu: true } } })
    await flushPromises()
    expect(w.text()).toContain('猫耳少女')
    expect(w.text()).toContain('修狗')
    await w.find('input').setValue('猫')
    await flushPromises()
    expect(w.text()).toContain('猫耳少女')
    expect(w.text()).not.toContain('修狗')
  })

  it('含跳转到提示词收藏的按钮', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => [] }) as any))
    const w = mount(CollectionListPage, { global: { stubs: { NMenu: true } } })
    await flushPromises()
    const btn = w.findAll('button').find(b => b.text().includes('去提示词收藏'))
    expect(btn).toBeTruthy()
  })

  it('卡片含删除按钮', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url === '/api/promptbox') {
        return { ok: true, json: async () => [{ id: 'c1', title: '待删', raw_prompt: 'x', categories: {}, extras: [], image_names: [], created_at: '', updated_at: '' }] } as any
      }
      return { ok: true, json: async () => ({}) } as any
    }))
    const w = mount(CollectionListPage, { global: { stubs: { NMenu: true } } })
    await flushPromises()
    expect(w.findAll('button').find(b => b.text().includes('删除'))).toBeTruthy()
  })
})
