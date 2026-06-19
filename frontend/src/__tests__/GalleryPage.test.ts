import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import GalleryPage from '../views/GalleryPage.vue'

vi.mock('naive-ui', async () => {
  const actual: any = await vi.importActual('naive-ui')
  return { ...actual, useMessage: () => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn() }) }
})

describe('GalleryPage', () => {
  it('渲染筛选面板与三个筛选标签', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ items: [], total: 0 }) }) as any))
    const w = mount(GalleryPage, { global: { stubs: { NImage: true } } })
    await flushPromises()
    expect(w.find('.filter-bar').exists()).toBe(true)
    const labels = w.find('.filter-bar').text()
    expect(labels).toContain('日期')
    expect(labels).toContain('标签')
    expect(labels).toContain('提示词')
  })
})
