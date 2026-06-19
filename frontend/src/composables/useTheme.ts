import { ref, computed } from 'vue'

export type ThemeMode = 'auto' | 'light' | 'dark'
const STORAGE_KEY = 'wd14.theme'

const mode = ref<ThemeMode>('auto')
const sysTick = ref(0)        // auto 模式下系统变化时递增以刷新 effective
let inited = false

function systemDark(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

function init() {
  if (inited || typeof window === 'undefined' || !window.matchMedia) return
  inited = true
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved === 'auto' || saved === 'light' || saved === 'dark') mode.value = saved
  const mq = window.matchMedia('(prefers-color-scheme: dark)')
  mq.addEventListener?.('change', () => { sysTick.value++ })
}

export function useTheme() {
  init()
  const effective = computed<'light' | 'dark'>(() => {
    void sysTick.value
    return mode.value === 'auto' ? (systemDark() ? 'dark' : 'light') : mode.value
  })
  function setMode(m: ThemeMode) {
    mode.value = m
    try { localStorage.setItem(STORAGE_KEY, m) } catch { /* 忽略隐私模式 */ }
  }
  return { mode, effective, setMode }
}
