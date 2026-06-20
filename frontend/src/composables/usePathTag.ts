import { reactive } from 'vue'
import { startPathTag, subscribePathTag } from '../api/client'

export type PathPhase = 'idle' | 'running' | 'done' | 'error'
export interface PathErrorItem { current: string; message: string }

interface PathTagState {
  phase: PathPhase
  total: number
  done: number
  ok: number
  skipped: number
  failed: number
  current: string
  jobId: string | null
  errors: PathErrorItem[]
}

const state = reactive<PathTagState>({
  phase: 'idle', total: 0, done: 0, ok: 0, skipped: 0, failed: 0,
  current: '', jobId: null, errors: [],
})

// EventSource 由 store 持有，不绑组件；subscribePathTag 返回带 close 的句柄
let es: { close: () => void } | null = null

function isBusy() {
  return state.phase === 'running'
}

function reset() {
  state.phase = 'idle'
  state.total = state.done = state.ok = state.skipped = state.failed = 0
  state.current = ''
  state.jobId = null
  state.errors = []
  es?.close()
  es = null
}

export interface PathTagStartOpts {
  path: string
  model: string
  genTh: number
  charTh: number
  useChar: boolean
  recursive: boolean
  onConflict: 'overwrite' | 'skip'
}

async function start(opts: PathTagStartOpts) {
  reset()
  state.phase = 'running'
  try {
    const r = await startPathTag({
      path: opts.path, model: opts.model, gen_th: opts.genTh, char_th: opts.charTh,
      use_char: opts.useChar, recursive: opts.recursive, on_conflict: opts.onConflict,
    })
    state.jobId = r.job_id
    state.total = r.total
  } catch (e) {
    // startPathTag 失败（路径非法/未知 model 等后端 400）：置 error，不进订阅
    state.phase = 'error'
    throw e
  }
  es = subscribePathTag(
    state.jobId!,
    (ev) => {
      if (ev.type === 'progress') {
        state.done = ev.done
        state.current = ev.current || ''
        if (ev.status === 'skip') state.skipped++
        else state.ok++
      } else if (ev.type === 'error') {
        state.failed++
        state.errors.push({ current: ev.current || '', message: ev.message || '' })
      } else if (ev.type === 'done') {
        state.phase = 'done'
        state.done = ev.done
        // 以 done 汇总为准（后端最终统计），兜底用当前累计值
        state.ok = ev.ok ?? state.ok
        state.skipped = ev.skipped ?? state.skipped
        state.failed = ev.errors ?? state.failed
        es?.close()
        es = null
      }
    },
    () => {
      // 连接断开：守卫 phase==='running'，避免覆盖 done 正常结束
      if (state.phase === 'running') {
        state.phase = 'error'
        es?.close()
        es = null
      }
    },
  )
}

export function usePathTag() {
  return { state, isBusy, start, reset }
}
