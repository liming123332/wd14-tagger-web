import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import RandomPage from '../views/RandomPage.vue'

// ImageCard 内部使用 useRouter/useMessage，需注入空 provider 以免挂载中断
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('naive-ui', async () => {
  const actual: any = await vi.importActual('naive-ui')
  return { ...actual, useMessage: () => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn() }) }
})

// mock 三个数据源 + 两个 toggle，记录调用以便断言源切换分发
// 注意：用 importActual 保留 fileUrl 等真实导出，否则 ImageCard 渲染时拿不到 fileUrl 会抛错。
const calls: string[] = []
vi.mock('../api/client', async () => {
  const actual: any = await vi.importActual('../api/client')
  return {
    ...actual,
    randomImages: vi.fn(async () => {
      // 真实图库 item 结构（见 api/client.ts 的 randomImages）：{id, source_name, tags, ...}，
      // 【没有 entry_key】。故意不伪造 entry_key——切源瞬间 source 已变、items 仍是图库 item
      // 的那一帧，若代码未防御，cardTo→parseEntryKey(undefined) 会在”切源不崩”用例里暴露崩溃。
      calls.push('randomImages'); return { items: [{ id: 'g1', source_name: 'g', tags: [] }] }
    }),
    listPromptbox: vi.fn(async () => {
      calls.push('listPromptbox')
      return [
        { id: 'p1', title: '收藏甲', raw_prompt: 'a, b', categories: {}, extras: [], image_names: [], created_at: '', updated_at: '' },
        { id: 'p2', title: '收藏乙', raw_prompt: 'c, d', categories: {}, extras: [], image_names: [], created_at: '', updated_at: '' },
      ]
    }),
  }
})
vi.mock('../api/characterfinder', async () => {
  const actual: any = await vi.importActual('../api/characterfinder')
  return {
    ...actual,
    randomCf: vi.fn(async (_t: string, _s: string) => {
      calls.push(`randomCf:${_t}:${_s}`); return { items: [{ entry_key: 'char:danbooru:k1', source: 'danbooru', name: 'n', favorite: false }] }
    }),
    toggleCharacterFavorite: vi.fn(async () => { calls.push('toggleChar'); return { favorite: true } }),
    toggleArtistFavorite: vi.fn(async () => { calls.push('toggleArtist'); return { favorite: true } }),
  }
})

describe('RandomPage 源切换', () => {
  beforeEach(() => { calls.length = 0; vi.clearAllMocks() })

  it('默认 source=gallery 调 randomImages', async () => {
    mount(RandomPage); await flushPromises()
    expect(calls).toContain('randomImages')
    expect(calls.some(c => c.startsWith('randomCf:'))).toBe(false)
  })

  it('切到 characters 调 randomCf("characters", cfSource)', async () => {
    const w = mount(RandomPage); await flushPromises()
    calls.length = 0
    // 源下拉是第一个 NSelect（naive-ui 组件 name 为 'Select'）；v-model:value 经 @update:value 触发
    const selects = w.findAllComponents({ name: 'Select' })
    await selects[0].vm.$emit('update:value', 'characters')
    await flushPromises()
    expect(calls.some(c => c === 'randomCf:characters:anima')).toBe(true)
  })

  it('切到 artists 调 randomCf("artists", cfSource)', async () => {
    const w = mount(RandomPage); await flushPromises()
    calls.length = 0
    const selects = w.findAllComponents({ name: 'Select' })
    await selects[0].vm.$emit('update:value', 'artists')
    await flushPromises()
    expect(calls.some(c => c === 'randomCf:artists:anima')).toBe(true)
  })

  it('角色源下切 cfSource=danbooru 重抽 randomCf characters danbooru', async () => {
    const w = mount(RandomPage); await flushPromises()
    // 切到 characters，cfSource 下拉才会渲染（默认 cfSource=anima）
    let selects = w.findAllComponents({ name: 'Select' })
    await selects[0].vm.$emit('update:value', 'characters'); await flushPromises()
    calls.length = 0
    // 切源后必须重新获取组件列表：v-if 渲染出的 cfSource 下拉不在旧数组里
    selects = w.findAllComponents({ name: 'Select' })
    await selects[1].vm.$emit('update:value', 'danbooru')
    await flushPromises()
    expect(calls.some(c => c === 'randomCf:characters:danbooru')).toBe(true)
  })

  it('图库非空时切到 characters 不崩（竞态：source 已变、旧 items 无 entry_key 的那一帧）', async () => {
    const w = mount(RandomPage); await flushPromises()
    // onMounted 后 items 是图库 item（无 entry_key）
    const selects = w.findAllComponents({ name: 'Select' })
    // 切源：source 同步变 characters，items 仍是图库 item 的那一帧，曾触发
    // cardTo→parseEntryKey(undefined)→.split(':') 崩溃。修复后应平滑过渡、不抛。
    await selects[0].vm.$emit('update:value', 'characters')
    await flushPromises()
    expect(calls.some(c => c === 'randomCf:characters:anima')).toBe(true)
  })

  it('切到 promptbox 调 listPromptbox，不调 randomImages/randomCf', async () => {
    const w = mount(RandomPage); await flushPromises()
    calls.length = 0
    const selects = w.findAllComponents({ name: 'Select' })
    await selects[0].vm.$emit('update:value', 'promptbox')
    await flushPromises()
    expect(calls).toContain('listPromptbox')
    expect(calls.some(c => c === 'randomImages')).toBe(false)
    expect(calls.some(c => c.startsWith('randomCf:'))).toBe(false)
  })

  it('promptbox 来源渲染收藏卡片标题', async () => {
    const w = mount(RandomPage); await flushPromises()
    const selects = w.findAllComponents({ name: 'Select' })
    await selects[0].vm.$emit('update:value', 'promptbox')
    await flushPromises()
    expect(w.text()).toContain('收藏甲')
    expect(w.text()).toContain('收藏乙')
  })

  it('promptbox 切源不崩（竞态：source 已变、items 异步替换的中间帧）', async () => {
    const w = mount(RandomPage); await flushPromises()
    const selects = w.findAllComponents({ name: 'Select' })
    await selects[0].vm.$emit('update:value', 'promptbox')
    await flushPromises()
    expect(calls.some(c => c === 'listPromptbox')).toBe(true)
  })
})
