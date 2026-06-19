import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import UploadPage from '../views/UploadPage.vue'
import { useBatch } from '../composables/useBatch'
import { NUpload } from 'naive-ui'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('naive-ui', async () => {
  const actual: any = await vi.importActual('naive-ui')
  return {
    ...actual,
    useMessage: () => ({ warning: vi.fn(), success: vi.fn(), error: vi.fn() }),
  }
})

describe('UploadPage', () => {
  beforeEach(() => { useBatch().reset() })

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

  it('选文件后显示「已选 N 张」并支持清空', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ ids: ['a'] }) }) as any))
    const w = mount(UploadPage, { global: { stubs: { NMenu: true } } })
    // 初始无汇总条
    expect(w.text()).not.toContain('已选')
    // 模拟 n-upload change：选了 2 个文件
    const up = w.findComponent(NUpload)
    await up.vm.$emit('change', {
      fileList: [{ file: new File(['x'], 'a.png') }, { file: new File(['y'], 'b.png') }],
    })
    await w.vm.$nextTick()
    expect(w.text()).toContain('已选 2 张')
    // 清空
    const clearBtn = w.findAll('button').find(b => b.text().includes('清空'))
    expect(clearBtn).toBeTruthy()
    await clearBtn!.trigger('click')
    await w.vm.$nextTick()
    expect(w.text()).not.toContain('已选')
  })
})
