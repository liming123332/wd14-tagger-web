import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { h } from 'vue'
import {
  IconUpload, IconGallery, IconCheck, IconCopy, IconDownload,
  IconSun, IconMoon, IconMonitor,
} from '../components/icons'

const wrap = (I: any) => mount({ render: () => h(I) })

describe('icons', () => {
  it.each([
    ['IconUpload', IconUpload], ['IconGallery', IconGallery],
    ['IconCheck', IconCheck], ['IconCopy', IconCopy], ['IconDownload', IconDownload],
  ])('%s 渲染一个 svg', (_name, I) => {
    expect(wrap(I).find('svg').exists()).toBe(true)
  })
  it('svg 用 currentColor 描边（随文字色继承）', () => {
    expect(wrap(IconCopy).find('svg').attributes('stroke')).toBe('currentColor')
  })
  it('主题三图标都存在', () => {
    expect(wrap(IconSun).find('svg').exists()).toBe(true)
    expect(wrap(IconMoon).find('svg').exists()).toBe(true)
    expect(wrap(IconMonitor).find('svg').exists()).toBe(true)
  })
  it('同一图标多次渲染互不干扰（每次新建 VNode，不复用）', () => {
    const N = 5
    const wrapper = mount({
      render: () => h('div', Array.from({ length: N }, () => h(IconCopy))),
    })
    expect(wrapper.findAll('svg').length).toBe(N)
  })
})
