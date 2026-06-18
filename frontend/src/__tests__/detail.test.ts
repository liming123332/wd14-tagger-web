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
})

describe('parsePhrase', () => {
  it('按逗号拆分', () => {
    expect(parsePhrase('long hair, blue eyes,smile')).toEqual(['long hair', 'blue eyes', 'smile'])
  })
  it('无逗号按空格拆', () => {
    expect(parsePhrase('long hair')).toEqual(['long hair'])
  })
  it('空串返回空', () => {
    expect(parsePhrase('')).toEqual([])
  })
})
