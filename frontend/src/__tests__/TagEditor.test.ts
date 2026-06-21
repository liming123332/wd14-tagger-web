import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('naive-ui', () => ({
  useMessage: () => ({ success: vi.fn(), warning: vi.fn(), error: vi.fn() }),
  NTag: { template: `<span class="n-tag"><slot/></span>` },
  NInput: { template: `<input/>` },
  NButton: {
    props: ['disabled'],
    emits: ['click'],
    template: `<button :disabled="disabled" @click="$emit('click')"><slot/></button>`,
  },
  NSpace: { template: `<div class="n-space"><slot/></div>` },
  NPopconfirm: { template: `<div class="n-popconfirm"><slot/><slot name="trigger"/></div>` },
}))

import TagEditor from '../components/TagEditor.vue'

const MODEL = (tags: string[] = ['long hair']) => ({ tags, phrase: tags.join(', '), user_edited: false })

describe('TagEditor', () => {
  beforeEach(() => { vi.unstubAllGlobals() })

  it('标签模式 + 非 extras：渲染「应用到分类词表」并 emit applyRule(当前 tags)', async () => {
    const w = mount(TagEditor, {
      props: { title: '角色头部', color: '#4CAF50', modelValue: MODEL(['long hair', 'blue eyes']), mode: 'tags', categoryKey: 'head' },
    })
    const btn = w.findAll('button').find(b => b.text().includes('应用到分类词表'))
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    const events = w.emitted('applyRule')
    expect(events).toBeTruthy()
    expect(events![0][0]).toEqual(['long hair', 'blue eyes'])
  })

  it('标签模式 + extras：不渲染「应用到分类词表」', () => {
    const w = mount(TagEditor, {
      props: { title: '未归类', color: '#9E9E9E', modelValue: MODEL(), mode: 'tags', categoryKey: 'extras' },
    })
    const btn = w.findAll('button').find(b => b.text().includes('应用到分类词表'))
    expect(btn).toBeFalsy()
  })

  it('短句模式：渲染「复制当前提示词」并写剪贴板为 phrase', async () => {
    const writeText = vi.fn(async () => undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    const w = mount(TagEditor, {
      props: { title: '角色头部', color: '#4CAF50', modelValue: { tags: ['long hair'], phrase: 'long hair, nice', user_edited: false }, mode: 'phrase', categoryKey: 'head' },
    })
    const btn = w.findAll('button').find(b => b.text().includes('复制当前提示词'))
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    expect(writeText).toHaveBeenCalledWith('long hair, nice')
  })
})

describe('TagEditor lockedTags', () => {
  beforeEach(() => vi.unstubAllGlobals())

  it('传 lockedTags 时渲染只读锁定标签（带 locked-tag 类，不可关闭）', () => {
    const w = mount(TagEditor, {
      props: {
        title: '角色头部', color: '#4CAF50',
        modelValue: MODEL(['long hair']), mode: 'tags', categoryKey: 'head',
        lockedTags: ['miku', 'vocaloid'],
      },
    })
    const locked = w.findAll('.locked-tag')
    expect(locked.length).toBe(2)
    expect(locked.map(t => t.text())).toEqual(['🔒 miku', '🔒 vocaloid'])
  })
  it('不传 lockedTags 时不渲染锁定标签', () => {
    const w = mount(TagEditor, {
      props: { title: '角色头部', color: '#4CAF50', modelValue: MODEL(['long hair']), mode: 'tags', categoryKey: 'head' },
    })
    expect(w.findAll('.locked-tag').length).toBe(0)
  })
  it('锁定标签不进入可编辑 tags（增删/拖拽不影响锁区）', () => {
    const w = mount(TagEditor, {
      props: {
        title: '角色头部', color: '#4CAF50',
        modelValue: MODEL(['long hair']), mode: 'tags', categoryKey: 'head',
        lockedTags: ['miku'],
      },
    })
    // 可编辑区 n-tag 不含 miku（锁区单独渲染）
    const editable = w.findAll('.n-tag').filter(t => !t.classes().includes('locked-tag'))
    expect(editable.map(t => t.text())).toEqual(['long hair'])
  })
})
