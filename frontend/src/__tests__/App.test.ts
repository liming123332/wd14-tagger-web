import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ path: '/gallery' }),
}))

import App from '../App.vue'
import BatchBadge from '../components/BatchBadge.vue'

const stubs = {
  NConfigProvider: { template: '<slot/>' },
  NMessageProvider: { template: '<slot/>' },
  NDialogProvider: { template: '<slot/>' },
  NLayout: { template: '<slot/>' },
  NLayoutSider: { template: '<div class="sider"><slot/></div>' },
  NLayoutContent: { template: '<div class="content-wrap"><slot/></div>' },
  NMenu: { template: '<div class="n-menu"/>' },
  NButton: { template: '<button @click="$emit(\'click\')"><slot/></button>' },
  NIcon: { template: '<i/>' },
  RouterView: { template: '<div class="router-view-stub"><slot :Component="null"/></div>' },
}

describe('App', () => {
  it('渲染侧栏骨架与 BatchBadge', () => {
    const w = mount(App, { global: { stubs } })
    expect(w.find('.sider').exists()).toBe(true)
    expect(w.findComponent(BatchBadge).exists()).toBe(true)
  })
  it('侧栏含品牌标识', () => {
    const w = mount(App, { global: { stubs } })
    expect(w.find('.brand').text()).toContain('WD14')
  })
  it('工具条显示当前页标题（图库）', () => {
    const w = mount(App, { global: { stubs } })
    expect(w.find('.topbar').text()).toContain('图库')
  })
})
