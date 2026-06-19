import { describe, it, expect, vi, beforeEach } from 'vitest'
import { uploadOne, listImages, randomImages, listTags, applyCategoryRules, tagImage, startBatch, listTaggers, downloadTagger, splitPrompt, listPromptbox, savePromptbox, deletePromptbox, analyzePromptbox } from '../api/client'

describe('uploadOne', () => {
  beforeEach(() => { vi.unstubAllGlobals() })
  it('单文件 POST /api/images 并返回 id', async () => {
    const fdSeen: any = []
    vi.stubGlobal('fetch', vi.fn(async (_url: string, opts: any) => {
      fdSeen.push(opts.body)
      return { ok: true, json: async () => ({ ids: ['abc123'] }) } as any
    }))
    const f = new File(['x'], 'a.png', { type: 'image/png' })
    const res = await uploadOne(f)
    expect(res).toEqual({ id: 'abc123' })
    expect(fdSeen[0]).toBeInstanceOf(FormData)
  })
  it('失败时抛错', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, text: async () => 'bad' }) as any))
    await expect(uploadOne(new File(['x'], 'a.png'))).rejects.toThrow('bad')
  })
  it('带 tags 时 FormData 含每个 tag', async () => {
    const fdSeen: any = []
    vi.stubGlobal('fetch', vi.fn(async (_url: string, opts: any) => {
      fdSeen.push(opts.body)
      return { ok: true, json: async () => ({ ids: ['id1'] }) } as any
    }))
    await uploadOne(new File(['x'], 'a.png'), ['t1', 't2'])
    expect(fdSeen[0]).toBeInstanceOf(FormData)
    expect(fdSeen[0].getAll('tags')).toEqual(['t1', 't2'])
  })
})

describe('listImages', () => {
  beforeEach(() => { vi.unstubAllGlobals() })
  it('带 date 时 URL 含 date 参数', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url)
      return { ok: true, json: async () => ({ items: [], total: 0 }) } as any
    }))
    await listImages(1, 24, '20260619')
    expect(urls[0]).toContain('date=20260619')
    expect(urls[0]).toContain('page=1')
    expect(urls[0]).toContain('size=24')
  })
  it('不带 date 时 URL 不含 date 参数', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url)
      return { ok: true, json: async () => ({ items: [], total: 0 }) } as any
    }))
    await listImages(2, 10)
    expect(urls[0]).not.toContain('date=')
    expect(urls[0]).toContain('page=2')
  })
  it('带 tags 时 URL 含每个 tag 参数', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url)
      return { ok: true, json: async () => ({ items: [], total: 0 }) } as any
    }))
    await listImages(1, 24, undefined, ['a', 'b'])
    expect(urls[0]).toContain('tags=a')
    expect(urls[0]).toContain('tags=b')
  })
  it('带 prompt 时按逗号/空格拆词，URL 含每个 prompt 参数', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url)
      return { ok: true, json: async () => ({ items: [], total: 0 }) } as any
    }))
    await listImages(1, 24, undefined, undefined, 'long hair, blue eyes')
    expect(urls[0]).toContain('prompt=long')
    expect(urls[0]).toContain('prompt=hair')
    expect(urls[0]).toContain('prompt=blue')
    expect(urls[0]).toContain('prompt=eyes')
  })
})

describe('randomImages', () => {
  beforeEach(() => { vi.unstubAllGlobals() })
  it('URL 含 random=true 与 size', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url)
      return { ok: true, json: async () => ({ items: [], total: 0 }) } as any
    }))
    await randomImages(12)
    expect(urls[0]).toContain('random=true')
    expect(urls[0]).toContain('size=12')
  })
})

describe('listTags', () => {
  beforeEach(() => { vi.unstubAllGlobals() })
  it('GET /api/images/tags 返回标签计数', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url)
      return { ok: true, json: async () => ({ fav: 3 }) } as any
    }))
    const r = await listTags()
    expect(urls[0]).toBe('/api/images/tags')
    expect(r).toEqual({ fav: 3 })
  })
})

describe('applyCategoryRules', () => {
  beforeEach(() => { vi.unstubAllGlobals() })
  it('PUT /api/config/rules/{cat} 携带 tags', async () => {
    const seen: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts: any) => {
      seen.push({ url, method: opts.method, body: opts.body })
      return { ok: true, json: async () => ({ category: 'head', exact: ['x'] }) } as any
    }))
    await applyCategoryRules('head', ['long hair', 'elf ears'])
    expect(seen[0].url).toBe('/api/config/rules/head')
    expect(seen[0].method).toBe('PUT')
    expect(JSON.parse(seen[0].body)).toEqual({ tags: ['long hair', 'elf ears'] })
  })
})

describe('tagImage', () => {
  beforeEach(() => { vi.unstubAllGlobals() })
  it('POST /api/images/{id}/tag 带 model', async () => {
    const seen: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts: any) => {
      seen.push({ url, body: opts.body })
      return { ok: true, json: async () => ({ id: 'x', model: 'wd3' }) } as any
    }))
    await tagImage('id1', 0.3, 0.9, 'wd3')
    expect(seen[0].url).toBe('/api/images/id1/tag')
    expect(JSON.parse(seen[0].body)).toMatchObject({ model: 'wd3', use_char: true })
  })
})

describe('startBatch', () => {
  beforeEach(() => { vi.unstubAllGlobals() })
  it('POST /api/batch/tag 带 model', async () => {
    const seen: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts: any) => {
      seen.push({ url, body: opts.body })
      return { ok: true, json: async () => ({ batch_id: 'B' }) } as any
    }))
    await startBatch(['a', 'b'], 0.35, 0.9, 'e621')
    expect(seen[0].url).toBe('/api/batch/tag')
    expect(JSON.parse(seen[0].body)).toMatchObject({ ids: ['a', 'b'], model: 'e621' })
  })
})

describe('listTaggers', () => {
  beforeEach(() => { vi.unstubAllGlobals() })
  it('GET /api/taggers 返回模型列表', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url)
      return { ok: true, json: async () => [{ key: 'wd14', label: 'WD14', downloaded: true }] } as any
    }))
    const r = await listTaggers()
    expect(urls[0]).toBe('/api/taggers')
    expect(r).toEqual([{ key: 'wd14', label: 'WD14', downloaded: true }])
  })
})

describe('downloadTagger', () => {
  beforeEach(() => { vi.unstubAllGlobals() })
  it('POST /api/taggers/{key}/download', async () => {
    const seen: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts: any) => {
      seen.push({ url, method: opts.method })
      return { ok: true, json: async () => ({ key: 'wd3', downloaded: true }) } as any
    }))
    const r = await downloadTagger('wd3')
    expect(seen[0].url).toBe('/api/taggers/wd3/download')
    expect(seen[0].method).toBe('POST')
    expect(r).toEqual({ key: 'wd3', downloaded: true })
  })
})

describe('splitPrompt', () => {
  beforeEach(() => { vi.unstubAllGlobals() })
  it('POST /api/promptbox/split 带 text', async () => {
    const seen: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts: any) => {
      seen.push({ url, body: opts.body })
      return { ok: true, json: async () => ({ categories: { head: ['long hair'] }, extras: [] }) } as any
    }))
    const r = await splitPrompt('long hair, dress')
    expect(seen[0].url).toBe('/api/promptbox/split')
    expect(JSON.parse(seen[0].body)).toEqual({ text: 'long hair, dress' })
    expect(r.categories.head).toEqual(['long hair'])
  })
})

describe('listPromptbox', () => {
  beforeEach(() => { vi.unstubAllGlobals() })
  it('GET /api/promptbox', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url)
      return { ok: true, json: async () => [{ id: 'x', title: 't' }] } as any
    }))
    const r = await listPromptbox()
    expect(urls[0]).toBe('/api/promptbox')
    expect(r.length).toBe(1)
  })
})

describe('savePromptbox', () => {
  beforeEach(() => { vi.unstubAllGlobals() })
  it('POST FormData 到 /api/promptbox', async () => {
    const seen: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts: any) => {
      seen.push({ url, body: opts.body })
      return { ok: true, json: async () => ({ id: 'x' }) } as any
    }))
    const fd = new FormData()
    fd.append('title', 't')
    await savePromptbox(fd)
    expect(seen[0].url).toBe('/api/promptbox')
    expect(seen[0].body).toBeInstanceOf(FormData)
  })
  it('失败时抛错', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, text: async () => 'bad' }) as any))
    await expect(savePromptbox(new FormData())).rejects.toThrow('bad')
  })
})

describe('deletePromptbox', () => {
  beforeEach(() => { vi.unstubAllGlobals() })
  it('DELETE /api/promptbox/{id}', async () => {
    const seen: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts: any) => {
      seen.push({ url, method: opts.method })
      return { ok: true, json: async () => ({ ok: true }) } as any
    }))
    await deletePromptbox('id1')
    expect(seen[0].url).toBe('/api/promptbox/id1')
    expect(seen[0].method).toBe('DELETE')
  })
})

describe('analyzePromptbox', () => {
  beforeEach(() => { vi.unstubAllGlobals() })
  it('POST FormData 到 /api/promptbox/analyze 带 model/gen_th/char_th', async () => {
    const seen: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts: any) => {
      seen.push({ url, body: opts.body })
      return { ok: true, json: async () => ({ items: [] }) } as any
    }))
    await analyzePromptbox([new File(['x'], 'a.png')], 'wd3', 0.3, 0.9)
    expect(seen[0].url).toBe('/api/promptbox/analyze')
    expect(seen[0].body).toBeInstanceOf(FormData)
    expect(seen[0].body.get('model')).toBe('wd3')
    expect(seen[0].body.get('gen_th')).toBe('0.3')
    expect(seen[0].body.get('char_th')).toBe('0.9')
  })
  it('失败时抛错', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, text: async () => 'bad' }) as any))
    await expect(analyzePromptbox([new File(['x'], 'a.png')], 'wd14', 0.35, 0.9)).rejects.toThrow('bad')
  })
})
