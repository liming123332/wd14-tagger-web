import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import BatchBadge from '../components/BatchBadge.vue'
import { useBatch } from '../composables/useBatch'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))

describe('BatchBadge', () => {
  it('idle 时不渲染', () => {
    useBatch().reset()
    const w = mount(BatchBadge)
    expect(w.find('[data-testid="badge"]').exists()).toBe(false)
  })
  it('处理中显示两段进度文本', async () => {
    const { state } = useBatch()
    state.phase = 'uploading'; state.total = 5; state.uploaded = 2; state.tagged = 1
    const w = mount(BatchBadge)
    const html = w.html()
    expect(html).toContain('2/5')
    expect(html).toContain('1/5')
  })
  it('done 显示完成', async () => {
    const { state } = useBatch()
    state.phase = 'done'; state.total = 3; state.uploaded = 3; state.tagged = 3
    const w = mount(BatchBadge)
    expect(w.html()).toContain('完成')
  })
})
