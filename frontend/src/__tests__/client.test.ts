import { describe, it, expect, vi, beforeEach } from 'vitest'
import { uploadOne } from '../api/client'

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
})
