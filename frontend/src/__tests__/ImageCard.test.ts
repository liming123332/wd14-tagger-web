import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

const push = vi.fn()
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))
vi.mock('naive-ui', () => ({
  useMessage: () => ({ success: vi.fn(), warning: vi.fn(), error: vi.fn() }),
  NCard: { template: `<div class="n-card"><slot/></div>` },
  NImage: { template: `<div class="n-image"/>` },
  NButton: {
    props: ['title'],
    emits: ['click'],
    template: `<button :title="title" @click="$emit('click', $event)"><slot/></button>`,
  },
  NTag: { template: `<span class="n-tag"><slot/></span>` },
}))

import ImageCard from '../components/ImageCard.vue'

const ITEM = { id: 'x', source_name: 'a.png', thumb: 't.webp', original: 'original.png', prompt: 'long hair' }

describe('ImageCard', () => {
  beforeEach(() => { vi.unstubAllGlobals(); push.mockClear() })

  it('渲染复制与下载两个按钮', () => {
    const w = mount(ImageCard, { props: { item: ITEM } })
    const titles = w.findAll('button').map(b => b.attributes('title'))
    expect(titles).toContain('复制完整 prompt')
    expect(titles).toContain('下载原图')
  })

  it('点击复制调用 clipboard.writeText(prompt)', async () => {
    const writeText = vi.fn(async () => undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    const w = mount(ImageCard, { props: { item: ITEM } })
    const copyBtn = w.findAll('button').find(b => b.attributes('title') === '复制完整 prompt')!
    await copyBtn.trigger('click')
    expect(writeText).toHaveBeenCalledWith('long hair')
  })

  it('prompt 为空时不调用 clipboard', async () => {
    const writeText = vi.fn(async () => undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    const w = mount(ImageCard, { props: { item: { ...ITEM, prompt: '' } } })
    const copyBtn = w.findAll('button').find(b => b.attributes('title') === '复制完整 prompt')!
    await copyBtn.trigger('click')
    expect(writeText).not.toHaveBeenCalled()
  })

  it('显示 item.tags 前 3 个 + +N', () => {
    const w = mount(ImageCard, { props: { item: { ...ITEM, tags: ['a', 'b', 'c', 'd', 'e'] } } })
    const tags = w.findAll('.n-tag').map(t => t.text())
    expect(tags).toEqual(['a', 'b', 'c', '+2'])
  })

  it('无 tags 时不渲染标签行', () => {
    const w = mount(ImageCard, { props: { item: ITEM } })
    expect(w.findAll('.n-tag').length).toBe(0)
  })
})

describe('ImageCard 通用化', () => {
  beforeEach(() => { vi.unstubAllGlobals(); push.mockClear() })

  it('传 to 时点击跳转到 to（而非默认 /detail/{id}）', async () => {
    const w = mount(ImageCard, { props: { item: { id: 'x' }, to: '/characters/danbooru/1' } })
    await w.find('.thumb').trigger('click')
    expect(push).toHaveBeenCalledWith('/characters/danbooru/1')
  })
  it('不传 to 时回退到 /detail/{id}', async () => {
    const w = mount(ImageCard, { props: { item: { id: 'abc' } } })
    await w.find('.thumb').trigger('click')
    expect(push).toHaveBeenCalledWith('/detail/abc')
  })
  it('传 imgSrc/titleText/tagsList 时覆盖默认字段', () => {
    const w = mount(ImageCard, {
      props: { item: {}, imgSrc: '/img/a.jpg', titleText: '初音', tagsList: ['1girl', 'singer', 'blue'] },
    })
    expect(w.find('.name').text()).toBe('初音')
    expect(w.findAll('.n-tag').map(t => t.text())).toEqual(['1girl', 'singer', 'blue'])
  })
  it('不传 favorite 时不渲染收藏按钮', () => {
    const w = mount(ImageCard, { props: { item: { id: 'x' } } })
    expect(w.findAll('button').some(b => b.attributes('title') === '收藏')).toBe(false)
  })
  it('传 favorite 时渲染收藏按钮，点击 emit toggle-favorite', async () => {
    const w = mount(ImageCard, { props: { item: { id: 'x' }, favorite: true } })
    const fav = w.findAll('button').find(b => b.attributes('title') === '收藏')!
    expect(fav).toBeTruthy()
    await fav.trigger('click')
    expect(w.emitted('toggle-favorite')).toBeTruthy()
  })
})
