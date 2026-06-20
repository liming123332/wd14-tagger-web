import { describe, it, expect, vi, beforeEach } from 'vitest'
import { usePathTag } from '../usePathTag'
import * as client from '../../api/client'

vi.mock('../../api/client', () => ({
  startPathTag: vi.fn(),
  subscribePathTag: vi.fn(),
}))

beforeEach(() => {
  usePathTag().reset()
  vi.clearAllMocks()
})

const OPTS = {
  path: 'I:/imgs', model: 'cl_tagger_v2', genTh: 0.55, charTh: 0.55,
  useChar: true, recursive: false, onConflict: 'overwrite' as const,
}

describe('usePathTag', () => {
  it('start 调 startPathTag + 订阅，progress 累计 ok/done，done 收尾', async () => {
    vi.mocked(client.startPathTag).mockResolvedValue({ job_id: 'J1', total: 2 })
    vi.mocked(client.subscribePathTag).mockImplementation((_id, onEvent: (e: any) => void) => {
      setTimeout(() => {
        onEvent({ type: 'progress', done: 1, total: 2, current: 'a.png', status: 'ok' })
        onEvent({ type: 'progress', done: 2, total: 2, current: 'b.png', status: 'ok' })
        onEvent({ type: 'done', done: 2, total: 2, ok: 2, skipped: 0, errors: 0 })
      }, 0)
      return { close: vi.fn() } as any
    })
    const { state, start, isBusy } = usePathTag()
    await start(OPTS)
    expect(state.phase).toBe('running')   // 订阅后立即返回，回调尚未跑
    expect(state.jobId).toBe('J1')
    expect(state.total).toBe(2)
    expect(isBusy()).toBe(true)
    await vi.waitFor(() => expect(state.phase).toBe('done'))
    expect(state.done).toBe(2)
    expect(state.ok).toBe(2)
  })

  it('skip 状态计入 skipped、ok 不增', async () => {
    vi.mocked(client.startPathTag).mockResolvedValue({ job_id: 'J1', total: 1 })
    vi.mocked(client.subscribePathTag).mockImplementation((_id, onEvent: any) => {
      setTimeout(() => {
        onEvent({ type: 'progress', done: 1, total: 1, current: 'a.png', status: 'skip' })
        onEvent({ type: 'done', done: 1, total: 1, ok: 0, skipped: 1, errors: 0 })
      }, 0)
      return { close: vi.fn() } as any
    })
    const { state, start } = usePathTag()
    await start({ ...OPTS, onConflict: 'skip' })
    await vi.waitFor(() => expect(state.phase).toBe('done'))
    expect(state.skipped).toBe(1)
    expect(state.ok).toBe(0)
  })

  it('error 事件 → failed++ 且 errors 记录 current/message', async () => {
    vi.mocked(client.startPathTag).mockResolvedValue({ job_id: 'J1', total: 1 })
    vi.mocked(client.subscribePathTag).mockImplementation((_id, onEvent: any) => {
      setTimeout(() => {
        onEvent({ type: 'error', current: 'bad.png', message: 'decode fail' })
        onEvent({ type: 'done', done: 1, total: 1, ok: 0, skipped: 0, errors: 1 })
      }, 0)
      return { close: vi.fn() } as any
    })
    const { state, start } = usePathTag()
    await start(OPTS)
    await vi.waitFor(() => expect(state.phase).toBe('done'))
    expect(state.failed).toBe(1)
    expect(state.errors[0]).toEqual({ current: 'bad.png', message: 'decode fail' })
  })

  it('start 失败（startPathTag reject）→ phase=error 且不订阅', async () => {
    vi.mocked(client.startPathTag).mockRejectedValue(new Error('400 path not found'))
    const { state, start } = usePathTag()
    await expect(start(OPTS)).rejects.toThrow('400')
    expect(client.subscribePathTag).not.toHaveBeenCalled()
    expect(state.phase).toBe('error')
  })

  it('SSE 断开（onDisconnect）不死锁：phase running→error，isBusy→false', async () => {
    vi.mocked(client.startPathTag).mockResolvedValue({ job_id: 'J1', total: 1 })
    let capturedDisconnect: (() => void) | null = null
    vi.mocked(client.subscribePathTag).mockImplementation(
      (_id: string, _onEvent: (e: any) => void, onDisconnect?: () => void) => {
        capturedDisconnect = onDisconnect ?? null
        return { close: vi.fn() } as any
      },
    )
    const { state, start, isBusy } = usePathTag()
    await start(OPTS)
    expect(state.phase).toBe('running')
    expect(isBusy()).toBe(true)
    expect(capturedDisconnect).not.toBeNull()
    capturedDisconnect!()
    expect(state.phase).toBe('error')
    expect(isBusy()).toBe(false)
  })

  it('reset 清空所有字段', async () => {
    vi.mocked(client.startPathTag).mockResolvedValue({ job_id: 'J1', total: 1 })
    const { state, start, reset } = usePathTag()
    await start(OPTS)
    reset()
    expect(state.phase).toBe('idle')
    expect(state.total).toBe(0)
    expect(state.errors).toEqual([])
  })
})
