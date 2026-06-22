import { reactive } from 'vue'
import {
  translateStatus, downloadTranslator, translateTags, unloadTranslator, getDownloadProgress,
} from '../api/client'

interface TranslatorState {
  downloaded: boolean
  loaded: boolean        // Llama 是否已加载进内存（首次翻译/下载后 true）
  downloading: boolean
  translating: boolean
  progress: any          // DownloadProgress | null（复用 tagger 同款 _state）
}

// 模块级单例（同 useTagger）：跨组件共享翻译状态 + 标签翻译缓存（英→中）。
// 缓存不落地——刷新页面即清空（符合「每次调用获取、不入库」要求），但同会话内避免重复请求。
const state = reactive<TranslatorState>({
  downloaded: false,
  loaded: false,
  downloading: false,
  translating: false,
  progress: null,
})

// 英文标签 → 中文释义。模块级 reactive，所有 TagEditor 共享同一份（同标签中文一致）。
const translations = reactive<Record<string, string>>({})

async function refreshStatus() {
  try {
    const s = await translateStatus()
    state.downloaded = s.downloaded
    state.loaded = s.loaded
  } catch { /* 忽略瞬时失败 */ }
}

// 下载翻译模型：轮询 getDownloadProgress 驱动 App.vue 全局浮层（与 tagger 下载同款 _state）。
async function download() {
  state.downloading = true
  state.progress = null
  const timer = setInterval(async () => {
    try { state.progress = await getDownloadProgress() } catch { /* 忽略轮询瞬时失败 */ }
  }, 500)
  try {
    await downloadTranslator()
    state.downloaded = true
    state.loaded = true // download 端点 ensure_loaded 会顺带加载
  } finally {
    clearInterval(timer)
    state.downloading = false
  }
}

// 翻译一批标签：未下载则先自动下载（首次触发）；只译未缓存的，结果合并进 translations。
// 返回这批标签的「英→中」映射（供调用方决定如何展示）。
async function translate(texts: string[]): Promise<Record<string, string>> {
  if (!texts.length) return {}
  // 首次：未下载则自动下载（下载进度走全局浮层）
  if (!state.downloaded) {
    await refreshStatus()
    if (!state.downloaded) {
      await download()
    }
  }
  // 只译未缓存的，避免重复请求
  const missing = Array.from(new Set(texts.filter(t => t && !(t in translations))))
  if (missing.length) {
    state.translating = true
    try {
      const { results } = await translateTags(missing)
      missing.forEach((t, i) => { translations[t] = (results[i] ?? t) })
      state.loaded = true
    } finally {
      state.translating = false
    }
  }
  const out: Record<string, string> = {}
  for (const t of texts) if (t && translations[t]) out[t] = translations[t]
  return out
}

async function unload() {
  try { await unloadTranslator(); state.loaded = false } catch { /* 忽略 */ }
}

export function useTranslator() {
  return { state, translations, refreshStatus, download, translate, unload }
}
