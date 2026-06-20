import { describe, it, expect } from 'vitest'
import { buildPrompt, parsePhrase } from '../detail-utils'

describe('buildPrompt', () => {
  it('按固定顺序拼接 6 类标签', () => {
    const meta = { categories: {
      scene: { tags: ['indoors'] }, quality: { tags: ['masterpiece'] },
      head: { tags: ['long hair'] }, clothing: { tags: ['dress'] },
      view: { tags: ['close-up'] }, action: { tags: ['sitting'] },
    } }
    expect(buildPrompt(meta)).toBe('masterpiece, long hair, dress, close-up, sitting, indoors')
  })
  it('跳过空类与空字符串标签', () => {
    const meta = { categories: {
      quality: { tags: [] }, head: { tags: ['long hair', ''] },
      clothing: { tags: ['dress'] }, view: { tags: [] },
      action: { tags: ['sitting'] }, scene: { tags: [] },
    } }
    expect(buildPrompt(meta)).toBe('long hair, dress, sitting')
  })
  it('包含未归类 extras 的标签（拼在末尾）', () => {
    const meta = { categories: {
      quality: { tags: ['masterpiece'] }, head: { tags: ['long hair'] },
      clothing: { tags: ['dress'] }, view: { tags: [] }, action: { tags: [] }, scene: { tags: [] },
    }, extras: { tags: ['uncategorized', 'extra tag'] } }
    expect(buildPrompt(meta)).toBe('masterpiece, long hair, dress, uncategorized, extra tag')
  })
})

describe('parsePhrase', () => {
  it('按逗号拆分', () => {
    expect(parsePhrase('long hair, blue eyes,smile')).toEqual(['long hair', 'blue eyes', 'smile'])
  })
  it('无逗号视为单个标签', () => {
    expect(parsePhrase('long hair')).toEqual(['long hair'])
  })
  it('空串返回空', () => {
    expect(parsePhrase('')).toEqual([])
  })
})
