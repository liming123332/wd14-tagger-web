import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useTagger } from '../useTagger'

beforeEach(() => {
  localStorage.clear()
  vi.unstubAllGlobals()
})

describe('useTagger', () => {
  it('默认选中 wd14', () => {
    const { state } = useTagger()
    expect(state.selected).toBe('wd14')
  })

  it('setSelected 写入 localStorage', () => {
    const { setSelected } = useTagger()
    setSelected('wd3')
    expect(localStorage.getItem('wd14-tagger.lastModel')).toBe('wd3')
  })

  it('启动时从 localStorage 恢复上次选择', async () => {
    localStorage.setItem('wd14-tagger.lastModel', 'e621')
    // 重新加载模块级 state：resetModules 清缓存后动态 import 触发模块重新初始化
    // （前端是 ESM 项目，用 import() 而非 require；vitest resetModules 对动态 import 生效）
    vi.resetModules()
    const { useTagger: fresh } = await import('../useTagger')
    expect(fresh().state.selected).toBe('e621')
  })

  it('refresh 拉取并填充 taggers', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true, json: async () => [
        { key: 'wd14', label: 'WD14', downloaded: true },
        { key: 'e621', label: 'E621', downloaded: false },
      ]
    }) as any))
    const { state, refresh } = useTagger()
    await refresh()
    expect(state.taggers.length).toBe(2)
    expect(state.taggers[0].label).toBe('WD14')
  })

  it('refresh 后若当前选中未下载则回退到首个已下载', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true, json: async () => [
        { key: 'wd14', label: 'WD14', downloaded: true },
        { key: 'e621', label: 'E621', downloaded: false },
      ]
    }) as any))
    const { state, setSelected, refresh } = useTagger()
    setSelected('e621')  // 未下载
    await refresh()
    expect(state.selected).toBe('wd14')  // 回退
  })

  it('download 调用接口后刷新状态', async () => {
    let downloadedKeys = new Set<string>()
    vi.stubGlobal('fetch', vi.fn(async (url: string, opts: any) => {
      if (opts?.method === 'POST' && url.includes('/download')) {
        downloadedKeys.add(url.split('/')[3])
      }
      return {
        ok: true, json: async () => {
          const all = ['wd14', 'wd3', 'wd_vit_v3', 'wd_eva_v3', 'wd_conv_v3', 'ddb', 'e621']
          return all.map(k => ({ key: k, label: k, downloaded: downloadedKeys.has(k) || k === 'wd14' }))
        }
      } as any
    }))
    const { state, download } = useTagger()
    await download('wd3')
    expect(state.downloading).toBeNull()
    expect(state.taggers.find(t => t.key === 'wd3')?.downloaded).toBe(true)
  })
})
