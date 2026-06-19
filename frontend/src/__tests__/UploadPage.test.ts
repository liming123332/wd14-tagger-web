import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import UploadPage from '../views/UploadPage.vue'
import { useBatch } from '../composables/useBatch'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('naive-ui', async () => {
  const actual: any = await vi.importActual('naive-ui')
  return {
    ...actual,
    useMessage: () => ({ warning: vi.fn(), success: vi.fn(), error: vi.fn() }),
  }
})

describe('UploadPage', () => {
  it('处理中禁用开始按钮', async () => {
    const { state } = useBatch()
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ ids: ['a'] }) }) as any))
    const w = mount(UploadPage, { global: { stubs: { NMenu: true } } })
    // 初始可点
    expect(w.find('[data-testid="start-btn"]').attributes('disabled')).toBeUndefined()
    // 触发处理中
    state.phase = 'uploading'
    await w.vm.$nextTick()
    expect(w.find('[data-testid="start-btn"]').attributes('disabled')).toBeDefined()
  })
})
