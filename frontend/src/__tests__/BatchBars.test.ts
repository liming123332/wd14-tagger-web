import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BatchBars from '../components/BatchBars.vue'

describe('BatchBars', () => {
  it('渲染上传与反推两段的数字', () => {
    const w = mount(BatchBars, { props: { uploaded: 2, tagged: 1, total: 5 } })
    const html = w.html()
    expect(html).toContain('2/5')   // 上传段
    expect(html).toContain('1/5')   // 反推段
  })
  it('total=0 时不抛错（百分比兜底为 0）', () => {
    const w = mount(BatchBars, { props: { uploaded: 0, tagged: 0, total: 0 } })
    expect(w.html()).toContain('0/0')
  })
})
