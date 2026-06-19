import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

// App.vue 用了 NMenu/useRouter，stub 掉 router
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

import App from '../App.vue'
import BatchBadge from '../components/BatchBadge.vue'

describe('App', () => {
  it('挂载了 BatchBadge（导航徽章存在）', () => {
    const w = mount(App, { global: { stubs: { NConfigProvider: { template: '<slot/>' }, NMessageProvider: { template: '<slot/>' }, NDialogProvider: { template: '<slot/>' }, NLayout: { template: '<slot/>' }, NMenu: { template: '<div/>' } } } })
    // idle 时徽章模板不渲染，但组件实例存在于树中
    expect(w.findComponent(BatchBadge).exists()).toBe(true)
  })
})
