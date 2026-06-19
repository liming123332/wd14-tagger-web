import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'

describe('test env', () => {
  it('能 mount 组件并读到 DOM', () => {
    const C = defineComponent({ setup: () => () => h('div', { id: 'x' }, 'hi') })
    const w = mount(C)
    expect(w.find('#x').text()).toBe('hi')
  })
})
