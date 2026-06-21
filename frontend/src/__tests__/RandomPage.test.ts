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
      // gallery item 也带 entry_key，避免切源瞬间（source 已变、items 尚未替换的那一帧）
      // cardTo→parseEntryKey(undefined) 抛错。不影响 gallery 分支断言。
      calls.push('randomImages'); return { items: [{ id: 'g1', source_name: 'g', tags: [], entry_key: 'gallery:g:g1' }] }
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
    expect(calls.some(c => c === 'randomCf:characters:danbooru')).toBe(true)
  })

  it('切到 artists 调 randomCf("artists", cfSource)', async () => {
    const w = mount(RandomPage); await flushPromises()
    calls.length = 0
    const selects = w.findAllComponents({ name: 'Select' })
    await selects[0].vm.$emit('update:value', 'artists')
    await flushPromises()
    expect(calls.some(c => c === 'randomCf:artists:danbooru')).toBe(true)
  })

  it('角色源下切 cfSource=anima 重抽 randomCf characters anima', async () => {
    const w = mount(RandomPage); await flushPromises()
    // 切到 characters，cfSource 下拉才会渲染
    let selects = w.findAllComponents({ name: 'Select' })
    await selects[0].vm.$emit('update:value', 'characters'); await flushPromises()
    calls.length = 0
    // 切源后必须重新获取组件列表：v-if 渲染出的 cfSource 下拉不在旧数组里
    selects = w.findAllComponents({ name: 'Select' })
    await selects[1].vm.$emit('update:value', 'anima')
    await flushPromises()
    expect(calls.some(c => c === 'randomCf:characters:anima')).toBe(true)
  })
})
