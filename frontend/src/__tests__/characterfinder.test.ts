import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  parseEntryKey, cfAssetUrl,
  searchCharacters, listCharacterSeries, getCharacter,
  tagCharacter, reclassifyCharacter, saveCharacter,
  uploadCharacterImage, toggleCharacterFavorite,
  searchArtists, getArtist, tagArtist, reclassifyArtist, saveArtist,
  uploadArtistImage, toggleArtistFavorite,
} from '../api/characterfinder'

describe('parseEntryKey', () => {
  it('拆 {kind}:{source}:{key}', () => {
    expect(parseEntryKey('char:danbooru:123')).toEqual({ kind: 'char', source: 'danbooru', key: '123' })
    expect(parseEntryKey('artist:anima:2b (nier_automata)')).toEqual({ kind: 'artist', source: 'anima', key: '2b (nier_automata)' })
  })
  it('key 含冒号时只切前两段', () => {
    expect(parseEntryKey('char:danbooru:a:b:c')).toEqual({ kind: 'char', source: 'danbooru', key: 'a:b:c' })
  })
})

describe('cfAssetUrl', () => {
  it('拼 /api/cf/asset 带 4 个 query', () => {
    expect(cfAssetUrl('char', 'danbooru', '123', 'thumb')).toBe('/api/cf/asset?kind=char&source=danbooru&key=123&which=thumb')
  })
  it('key 含特殊字符时编码', () => {
    expect(cfAssetUrl('char', 'anima', '2b (nier)', 'image')).toBe('/api/cf/asset?kind=char&source=anima&key=2b%20(nier)&which=image')
  })
})

describe('searchCharacters', () => {
  beforeEach(() => vi.unstubAllGlobals())
  it('GET /api/cf/characters 带 source/page/size，series 可选', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url); return { ok: true, json: async () => ({ items: [], total: 0 }) } as any
    }))
    await searchCharacters('miku', 'danbooru', 'vocaloid', 2, 50)
    expect(urls[0]).toContain('/api/cf/characters?')
    expect(urls[0]).toContain('query=miku')
    expect(urls[0]).toContain('source=danbooru')
    expect(urls[0]).toContain('series=vocaloid')
    expect(urls[0]).toContain('page=2')
    expect(urls[0]).toContain('size=50')
  })
  it('无 series 时不带 series 参数', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url); return { ok: true, json: async () => ({ items: [], total: 0 }) } as any
    }))
    await searchCharacters('', 'anima')
    expect(urls[0]).not.toContain('series=')
  })
})

describe('listCharacterSeries', () => {
  beforeEach(() => vi.unstubAllGlobals())
  it('GET /api/cf/characters/series?source=', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url); return { ok: true, json: async () => [{ series: 'vocaloid', count: 3 }] } as any
    }))
    const r = await listCharacterSeries('danbooru')
    expect(urls[0]).toBe('/api/cf/characters/series?source=danbooru')
    expect(r[0]).toEqual({ series: 'vocaloid', count: 3 })
  })
})

describe('getCharacter', () => {
  beforeEach(() => vi.unstubAllGlobals())
  it('GET /api/cf/character?source=&key=，key 编码', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url); return { ok: true, json: async () => ({ entry_key: 'x' }) } as any
    }))
    await getCharacter('anima', '2b (nier)')
    expect(urls[0]).toBe('/api/cf/character?source=anima&key=2b%20(nier)')
  })
})

describe('tagCharacter', () => {
  beforeEach(() => vi.unstubAllGlobals())
  it('POST /api/cf/character/tag?source=&key= 带 model/gen_th/char_th/use_char', async () => {
    const seen: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts: any) => {
      seen.push({ url, body: opts.body }); return { ok: true, json: async () => ({}) } as any
    }))
    await tagCharacter('danbooru', '1', 0.35, 0.9, 'wd14')
    expect(seen[0].url).toBe('/api/cf/character/tag?source=danbooru&key=1')
    expect(JSON.parse(seen[0].body)).toMatchObject({ model: 'wd14', gen_th: 0.35, char_th: 0.9, use_char: true })
  })
})

describe('reclassifyCharacter', () => {
  beforeEach(() => vi.unstubAllGlobals())
  it('POST /api/cf/character/reclassify 带 keep', async () => {
    const seen: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts: any) => {
      seen.push({ url, body: opts.body }); return { ok: true, json: async () => ({}) } as any
    }))
    await reclassifyCharacter('danbooru', '1', { head: ['my tag'] })
    expect(seen[0].url).toBe('/api/cf/character/reclassify?source=danbooru&key=1')
    expect(JSON.parse(seen[0].body)).toEqual({ keep: { head: ['my tag'] } })
  })
})

describe('saveCharacter', () => {
  beforeEach(() => vi.unstubAllGlobals())
  it('PUT /api/cf/character body 含 categories/extras/custom_tags，不含 locked_tags', async () => {
    const seen: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts: any) => {
      seen.push({ url, method: opts.method, body: opts.body }); return { ok: true, json: async () => ({}) } as any
    }))
    await saveCharacter('danbooru', '1', {
      categories: { head: { tags: ['x'], phrase: 'x', user_edited: true } },
      extras: { tags: [], phrase: '', user_edited: false },
      custom_tags: ['fav'],
    })
    expect(seen[0].url).toBe('/api/cf/character?source=danbooru&key=1')
    expect(seen[0].method).toBe('PUT')
    const body = JSON.parse(seen[0].body)
    expect(body.categories.head.tags).toEqual(['x'])
    expect(body.custom_tags).toEqual(['fav'])
    expect(body.locked_tags).toBeUndefined()  // 锁定标签绝不发回后端
  })
})

describe('uploadCharacterImage', () => {
  beforeEach(() => vi.unstubAllGlobals())
  it('POST FormData 到 /api/cf/character/image', async () => {
    const seen: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts: any) => {
      seen.push({ url, body: opts.body }); return { ok: true, json: async () => ({ image_override: 'a.png' }) } as any
    }))
    const r = await uploadCharacterImage('danbooru', '1', new File(['x'], 'a.png'))
    expect(seen[0].url).toBe('/api/cf/character/image?source=danbooru&key=1')
    expect(seen[0].body).toBeInstanceOf(FormData)
    expect(seen[0].body.get('file')).toBeTruthy()
    expect(r).toEqual({ image_override: 'a.png' })
  })
})

describe('toggleCharacterFavorite', () => {
  beforeEach(() => vi.unstubAllGlobals())
  it('POST /api/cf/character/favorite 返回 {favorite}', async () => {
    const seen: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts: any) => {
      seen.push({ url, method: opts.method }); return { ok: true, json: async () => ({ favorite: true }) } as any
    }))
    const r = await toggleCharacterFavorite('danbooru', '1')
    expect(seen[0].url).toBe('/api/cf/character/favorite?source=danbooru&key=1')
    expect(seen[0].method).toBe('POST')
    expect(r).toEqual({ favorite: true })
  })
})

describe('artists 同构', () => {
  beforeEach(() => vi.unstubAllGlobals())
  it('searchArtists → /api/cf/artists', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url); return { ok: true, json: async () => ({ items: [], total: 0 }) } as any
    }))
    await searchArtists('ebi', 'danbooru', 1, 50)
    expect(urls[0]).toContain('/api/cf/artists?')
    expect(urls[0]).toContain('query=ebi')
  })
  it('getArtist → /api/cf/artist（单数）', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url); return { ok: true, json: async () => ({}) } as any
    }))
    await getArtist('danbooru', '1')
    expect(urls[0]).toBe('/api/cf/artist?source=danbooru&key=1')
  })
  it('tagArtist → /api/cf/artist/tag', async () => {
    const seen: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts: any) => {
      seen.push({ url, body: opts.body }); return { ok: true, json: async () => ({}) } as any
    }))
    await tagArtist('danbooru', '1', 0.35, 0.9, 'wd14')
    expect(seen[0].url).toBe('/api/cf/artist/tag?source=danbooru&key=1')
  })
  it('saveArtist PUT 不含 locked_tags', async () => {
    const seen: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (_url: string, opts: any) => {
      seen.push({ body: opts.body }); return { ok: true, json: async () => ({}) } as any
    }))
    await saveArtist('danbooru', '1', { categories: {}, extras: { tags: [], phrase: '', user_edited: false }, custom_tags: [] })
    expect(JSON.parse(seen[0].body).locked_tags).toBeUndefined()
  })
  it('uploadArtistImage / toggleArtistFavorite 路径', async () => {
    const urls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url); return { ok: true, json: async () => ({}) } as any
    }))
    await uploadArtistImage('danbooru', '1', new File(['x'], 'a.png'))
    await toggleArtistFavorite('danbooru', '1')
    expect(urls[0]).toBe('/api/cf/artist/image?source=danbooru&key=1')
    expect(urls[1]).toBe('/api/cf/artist/favorite?source=danbooru&key=1')
  })
  it('reclassifyArtist 带 keep', async () => {
    const seen: any[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts: any) => {
      seen.push({ url, body: opts.body }); return { ok: true, json: async () => ({}) } as any
    }))
    await reclassifyArtist('danbooru', '1', { clothing: ['suit'] })
    expect(seen[0].url).toBe('/api/cf/artist/reclassify?source=danbooru&key=1')
    expect(JSON.parse(seen[0].body)).toEqual({ keep: { clothing: ['suit'] } })
  })
})
