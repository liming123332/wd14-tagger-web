import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
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
  beforeEach(() => { vi.unstubAllGlobals() })

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
