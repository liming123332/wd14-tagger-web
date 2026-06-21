import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import CfFavoritesPage from '../views/CfFavoritesPage.vue'

// ImageCard 内部用 useRouter/useMessage/fileUrl，需注入 provider + importActual 保留真实导出
// （naive-ui 真实组件需保留，findAllComponents({name:'ImageCard'}) 才能命中）
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('naive-ui', async () => {
  const actual: any = await vi.importActual('naive-ui')
  return { ...actual, useMessage: () => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn() }) }
})
vi.mock('../api/client', async () => ({ ...(await vi.importActual('../api/client')) }))

const favData: Record<string, any> = {
  char: { items: [
    { entry_key: 'char:danbooru:1', source: 'danbooru', name: 'Hatsune Miku', core_tags: 'vocaloid,twins', favorite: true },
    { entry_key: 'char:danbooru:2', source: 'danbooru', name: 'Kafka', core_tags: 'hsr', favorite: true },
  ] },
  artist: { items: [
    { entry_key: 'artist:anima:a1', source: 'anima', name: 'Artist One', tag: 'cool', favorite: true },
  ] },
}

// importActual 保留 parseEntryKey（cardTo 渲染时用），仅覆盖 listCfFavorites + 两 toggle
vi.mock('../api/characterfinder', async () => {
  const actual: any = await vi.importActual('../api/characterfinder')
  return {
    ...actual,
    listCfFavorites: vi.fn(async (kind: string) => favData[kind] || { items: [] }),
    toggleCharacterFavorite: vi.fn(async () => ({ favorite: false })),
    toggleArtistFavorite: vi.fn(async () => ({ favorite: false })),
  }
})

import { listCfFavorites, toggleCharacterFavorite } from '../api/characterfinder'

describe('CfFavoritesPage', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('默认 kind=char 加载角色收藏', async () => {
    mount(CfFavoritesPage); await flushPromises()
    expect(listCfFavorites).toHaveBeenCalledWith('char')
  })

  it('切 tab 到 artist 加载艺术家收藏', async () => {
    const w = mount(CfFavoritesPage); await flushPromises()
    ;(listCfFavorites as any).mockClear()
    // naive-ui NTabs 真实 name 为 'Tabs'；v-model:value 经 @update:value 触发
    await w.findComponent({ name: 'Tabs' }).vm.$emit('update:value', 'artist')
    await flushPromises()
    expect(listCfFavorites).toHaveBeenCalledWith('artist')
  })

  it('渲染收藏项卡片（角色 2 项）', async () => {
    const w = mount(CfFavoritesPage); await flushPromises()
    const cards = w.findAllComponents({ name: 'ImageCard' })
    expect(cards.length).toBe(2)
  })

  it('toggle 收藏后乐观移除该卡', async () => {
    const w = mount(CfFavoritesPage); await flushPromises()
    expect(w.findAllComponents({ name: 'ImageCard' }).length).toBe(2)
    const card = w.findAllComponents({ name: 'ImageCard' })[0]
    await card.vm.$emit('toggle-favorite')
    await flushPromises()  // onToggleFav 是 async，需 flush 等 filter 生效
    expect(toggleCharacterFavorite).toHaveBeenCalled()
    expect(w.findAllComponents({ name: 'ImageCard' }).length).toBe(1)
  })

  it('前端搜索过滤 name', async () => {
    const w = mount(CfFavoritesPage); await flushPromises()
    // naive-ui NInput 真实 name 为 'Input'
    const input = w.findComponent({ name: 'Input' })
    await input.vm.$emit('update:value', 'kafka')
    await flushPromises()
    const cards = w.findAllComponents({ name: 'ImageCard' })
    expect(cards.length).toBe(1)
  })
})
