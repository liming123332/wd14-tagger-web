import { reactive } from 'vue'
import { listTaggers, downloadTagger, unloadAllTaggers, type TaggerInfo } from '../api/client'

const LS_KEY = 'wd14-tagger.lastModel'
const DEFAULT_MODEL = 'wd14'

interface TaggerState {
  selected: string
  taggers: TaggerInfo[]
  downloading: string | null
  unloading: boolean
}

// 模块级单例（同 useBatch）：跨组件共享当前选中模型。
const state = reactive<TaggerState>({
  selected: localStorage.getItem(LS_KEY) || DEFAULT_MODEL,
  taggers: [],
  downloading: null,
  unloading: false,
})

function persist() {
  try { localStorage.setItem(LS_KEY, state.selected) } catch { /* 忽略隐私模式等 */ }
}

function setSelected(key: string) {
  state.selected = key
  persist()
}

async function refresh() {
  try {
    state.taggers = await listTaggers()
  } catch {
    state.taggers = []
  }
  // 当前选中若不在列表或未下载，回退到首个已下载（列表非空时）
  if (state.taggers.length) {
    const ok = state.taggers.some(t => t.key === state.selected && t.downloaded)
    if (!ok) {
      const first = state.taggers.find(t => t.downloaded)
      setSelected(first ? first.key : DEFAULT_MODEL)
    }
  }
}

function isDownloaded(key: string): boolean {
  return state.taggers.some(t => t.key === key && t.downloaded)
}

async function download(key: string) {
  state.downloading = key
  try {
    await downloadTagger(key)
    await refresh()
  } finally {
    state.downloading = null
  }
}

// 卸载所有已加载模型（从内存/显存释放 ONNX session，不删文件；下次反推重新加载）。
// 不需要 refresh——下载状态（文件在不在）没变，仅后端内存态变了。
async function unloadAll() {
  state.unloading = true
  try {
    await unloadAllTaggers()
  } finally {
    state.unloading = false
  }
}

export function useTagger() {
  return { state, setSelected, refresh, isDownloaded, download, unloadAll }
}
