import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import UploadPage from '../views/UploadPage.vue'
import { useBatch } from '../composables/useBatch'
import { NUpload } from 'naive-ui'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('naive-ui', async () => {
  const actual: any = await vi.importActual('naive-ui')
  return {
    ...actual,
    useMessage: () => ({ warning: vi.fn(), success: vi.fn(), error: vi.fn() }),
  }
})

// mock useTagger：避免 onMounted refresh 触发真 fetch，并让 selected/taggers 可控。
const taggerState: any = {
  selected: 'wd14',
  taggers: [{ key: 'wd14', label: 'WD14', downloaded: true }],
  downloading: null,
}
vi.mock('../composables/useTagger', () => ({
  useTagger: () => ({
    state: taggerState,
    setSelected: vi.fn((k: string) => { taggerState.selected = k }),
    refresh: vi.fn(async () => {}),
    isDownloaded: (k: string) => taggerState.taggers.some((t: any) => t.key === k && t.downloaded),
    download: vi.fn(async () => {}),
  }),
}))

describe('UploadPage', () => {
  beforeEach(() => {
    useBatch().reset()
    taggerState.selected = 'wd14'
    taggerState.taggers = [{ key: 'wd14', label: 'WD14', downloaded: true }]
    taggerState.downloading = null
  })

  it('处理中禁用开始按钮', async () => {
    const { state } = useBatch()
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ ids: ['a'] }) }) as any))
    const w = mount(UploadPage, { global: { stubs: { NMenu: true } } })
    expect(w.find('[data-testid="start-btn"]').attributes('disabled')).toBeUndefined()
    state.phase = 'uploading'
    await w.vm.$nextTick()
    expect(w.find('[data-testid="start-btn"]').attributes('disabled')).toBeDefined()
  })

  it('选文件后显示「已选 N 张」并支持清空', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ ids: ['a'] }) }) as any))
    const w = mount(UploadPage, { global: { stubs: { NMenu: true } } })
    expect(w.text()).not.toContain('已选')
    const up = w.findComponent(NUpload)
    await up.vm.$emit('change', {
      fileList: [{ file: new File(['x'], 'a.png') }, { file: new File(['y'], 'b.png') }],
    })
    await w.vm.$nextTick()
    expect(w.text()).toContain('已选 2 张')
    const clearBtn = w.findAll('button').find(b => b.text().includes('清空'))
    expect(clearBtn).toBeTruthy()
    await clearBtn!.trigger('click')
    await w.vm.$nextTick()
    expect(w.text()).not.toContain('已选')
  })

  it('选中未下载模型时显示「未下载」与下载按钮', async () => {
    taggerState.taggers = [
      { key: 'wd14', label: 'WD14', downloaded: true },
      { key: 'e621', label: 'E621', downloaded: false },
    ]
    taggerState.selected = 'e621'
    const w = mount(UploadPage, { global: { stubs: { NMenu: true } } })
    await w.vm.$nextTick()
    expect(w.text()).toContain('未下载')
    expect(w.findAll('button').some(b => b.text().includes('下载'))).toBe(true)
  })

  it('选中已下载模型时不显示「未下载」提示', async () => {
    taggerState.taggers = [{ key: 'wd14', label: 'WD14', downloaded: true }]
    taggerState.selected = 'wd14'
    const w = mount(UploadPage, { global: { stubs: { NMenu: true } } })
    await w.vm.$nextTick()
    expect(w.text()).not.toContain('未下载')
  })

  it('选中 cl_tagger 时角色阈值标签变为「角色名称识别阈值（仅 cl_tagger 生效）」', async () => {
    taggerState.taggers = [
      { key: 'wd14', label: 'WD14', downloaded: true },
      { key: 'cl_tagger', label: 'CL Tagger', downloaded: true },
    ]
    taggerState.selected = 'cl_tagger'
    const w = mount(UploadPage, { global: { stubs: { NMenu: true } } })
    await w.vm.$nextTick()
    expect(w.text()).toContain('角色名称识别阈值（仅 cl_tagger 生效）')
  })

  it('render-label 为 prop：选中已下载模型时 trigger 渲染「已下载」NTag', async () => {
    taggerState.taggers = [{ key: 'wd14', label: 'WD14', downloaded: true }]
    taggerState.selected = 'wd14'
    const w = mount(UploadPage, { global: { stubs: { NMenu: true } } })
    await w.vm.$nextTick()
    // render-label 是 prop，trigger 也调用它 → 「已下载」文本出现在关闭态
    expect(w.text()).toContain('已下载')
  })
})
