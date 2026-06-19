import { reactive } from 'vue'
import { uploadOne, startBatch, subscribeBatch } from '../api/client'

export type Phase = 'idle' | 'uploading' | 'tagging' | 'done' | 'error'
export interface BatchItem { id: string; name: string; status: 'pending' | 'ok' | 'error'; msg?: string }

interface BatchState {
  phase: Phase
  total: number
  uploaded: number
  tagged: number
  failed: number
  current: string
  batchId: string | null
  items: BatchItem[]
}

const state = reactive<BatchState>({
  phase: 'idle', total: 0, uploaded: 0, tagged: 0, failed: 0,
  current: '', batchId: null, items: [],
})

// EventSource 由 store 持有，不绑组件；subscribeBatch 返回带 close 的句柄
let es: { close: () => void } | null = null

function isBusy() {
  return state.phase === 'uploading' || state.phase === 'tagging'
}

function reset() {
  state.phase = 'idle'
  state.total = state.uploaded = state.tagged = state.failed = 0
  state.current = ''
  state.batchId = null
  state.items = []
  es?.close()
  es = null
}

async function start(files: File[], autoTag: boolean, genTh: number, charTh: number) {
  reset()
  state.phase = 'uploading'
  state.total = files.length
  state.items = files.map(f => ({ id: '', name: f.name, status: 'pending' as const }))
  const ids: string[] = []
  for (let i = 0; i < files.length; i++) {
    try {
      const res = await uploadOne(files[i])
      state.uploaded++
      state.items[i].id = res.id
      ids.push(res.id)
    } catch (e: any) {
      state.items[i].status = 'error'
      state.items[i].msg = e?.message || String(e)
    }
  }
  if (ids.length === 0) { state.phase = 'error'; return }
  if (!autoTag) {
    state.items.forEach(it => { if (it.status === 'pending') it.status = 'ok' })
    state.phase = 'done'
    return
  }
  const b = await startBatch(ids, genTh, charTh)
  state.batchId = b.batch_id
  state.phase = 'tagging'
  // 推迟到下一微任务再订阅，确保 start() 返回后调用方先读到 phase='tagging'，
  // 其后才触发 SSE 回调（与 EventSource 真实异步语义一致）。
  Promise.resolve().then(() => {
    es = subscribeBatch(b.batch_id, (ev) => {
      if (ev.type === 'progress') {
        state.tagged++
        state.current = ev.current || ''
        const it = state.items.find(x => x.id === ev.id)
        if (it) it.status = 'ok'
      } else if (ev.type === 'error') {
        state.failed++
        const it = state.items.find(x => x.id === ev.id)
        if (it) { it.status = 'error'; it.msg = ev.message || '' }
      } else if (ev.type === 'done') {
        state.phase = 'done'
        es?.close()
        es = null
      }
    })
  })
}

export function useBatch() {
  return { state, isBusy, start, reset }
}
