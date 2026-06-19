import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BatchDetailPage from '../views/BatchDetailPage.vue'
import { useBatch } from '../composables/useBatch'

describe('BatchDetailPage', () => {
  it('渲染统计与 items 明细', () => {
    const { state } = useBatch()
    state.phase = 'tagging'
    state.total = 2; state.uploaded = 2; state.tagged = 1; state.failed = 0
    state.items = [
      { id: 'a', name: 'a.png', status: 'ok' },
      { id: 'b', name: 'b.png', status: 'pending' },
    ]
    const w = mount(BatchDetailPage)
    const html = w.html()
    expect(html).toContain('a.png')
    expect(html).toContain('b.png')
    expect(html).toContain('1/2')   // 反推进度 1/2
  })
})
