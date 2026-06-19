import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useBatch } from '../useBatch'
import * as client from '../../api/client'

vi.mock('../../api/client', () => ({
  uploadOne: vi.fn(),
  startBatch: vi.fn(),
  subscribeBatch: vi.fn(),
}))

beforeEach(() => {
  useBatch().reset()
  vi.clearAllMocks()
})

describe('useBatch', () => {
  it('逐张上传，autoTag=false 直接 done 且 items 标 ok', async () => {
    vi.mocked(client.uploadOne)
      .mockResolvedValueOnce({ id: 'a' })
      .mockResolvedValueOnce({ id: 'b' })
    const { state, start, isBusy } = useBatch()
    await start([new File([], 'x.png'), new File([], 'y.png')], false, 0.35, 0.9)
    expect(state.phase).toBe('done')
    expect(state.total).toBe(2)
    expect(state.uploaded).toBe(2)
    expect(state.tagged).toBe(0)
    expect(state.items.map(i => i.status)).toEqual(['ok', 'ok'])
    expect(client.startBatch).not.toHaveBeenCalled()
    expect(isBusy()).toBe(false)
  })

  it('单张上传失败记 error，其余继续', async () => {
    vi.mocked(client.uploadOne)
      .mockRejectedValueOnce(new Error('boom'))
      .mockResolvedValueOnce({ id: 'b' })
    const { state, start } = useBatch()
    await start([new File([], 'x.png'), new File([], 'y.png')], false, 0.35, 0.9)
    expect(state.uploaded).toBe(1)
    expect(state.items[0].status).toBe('error')
    expect(state.items[0].msg).toBe('boom')
    expect(state.items[1].status).toBe('ok')
  })

  it('全部上传失败 → phase=error', async () => {
    vi.mocked(client.uploadOne).mockRejectedValue(new Error('x'))
    const { state, start } = useBatch()
    await start([new File([], 'x.png')], true, 0.35, 0.9)
    expect(state.phase).toBe('error')
    expect(client.startBatch).not.toHaveBeenCalled()
  })

  it('autoTag=true：上传后 startBatch + 订阅 SSE，progress/done 更新', async () => {
    vi.mocked(client.uploadOne).mockResolvedValue({ id: 'a' })
    vi.mocked(client.startBatch).mockResolvedValue({ batch_id: 'B1' })
    vi.mocked(client.subscribeBatch).mockImplementation((_id: string, onEvent: (e: any) => void) => {
      // 真实 EventSource.onmessage 是宏任务级网络回调，用 setTimeout 如实模拟
      setTimeout(() => {
        onEvent({ type: 'progress', done: 1, total: 1, current: 'x.png', id: 'a' })
        onEvent({ type: 'done', ok: 1, failed: 0 })
      }, 0)
      return { close: vi.fn() } as any
    })
    const { state, start, isBusy } = useBatch()
    await start([new File([], 'x.png')], true, 0.35, 0.9)
    expect(state.phase).toBe('tagging')   // 订阅后立即返回，回调尚未跑
    expect(state.batchId).toBe('B1')
    expect(isBusy()).toBe(true)
    await vi.waitFor(() => expect(state.phase).toBe('done'))
    expect(state.tagged).toBe(1)
    expect(state.items[0].status).toBe('ok')
  })

  it('SSE error 事件 → failed++ 且 items 标 error', async () => {
    vi.mocked(client.uploadOne).mockResolvedValue({ id: 'a' })
    vi.mocked(client.startBatch).mockResolvedValue({ batch_id: 'B1' })
    vi.mocked(client.subscribeBatch).mockImplementation((_id, onEvent: any) => {
      setTimeout(() => {
        onEvent({ type: 'error', id: 'a', message: 'timeout' })
        onEvent({ type: 'done', ok: 0, failed: 1 })
      }, 0)
      return { close: vi.fn() } as any
    })
    const { state, start } = useBatch()
    await start([new File([], 'x.png')], true, 0.35, 0.9)
    await vi.waitFor(() => expect(state.phase).toBe('done'))
    expect(state.failed).toBe(1)
    expect(state.items[0].status).toBe('error')
    expect(state.items[0].msg).toBe('timeout')
  })

  it('SSE 连接断开（onDisconnect）不死锁：phase 由 tagging→error，isBusy→false', async () => {
    vi.mocked(client.uploadOne).mockResolvedValue({ id: 'a' })
    vi.mocked(client.startBatch).mockResolvedValue({ batch_id: 'B1' })
    let capturedDisconnect: (() => void) | null = null
    vi.mocked(client.subscribeBatch).mockImplementation(
      (_id: string, _onEvent: (e: any) => void, onDisconnect?: () => void) => {
        capturedDisconnect = onDisconnect ?? null
        return { close: vi.fn() } as any
      },
    )
    const { state, start, isBusy } = useBatch()
    await start([new File([], 'x.png')], true, 0.35, 0.9)
    expect(state.phase).toBe('tagging')
    expect(isBusy()).toBe(true)
    expect(capturedDisconnect).not.toBeNull()
    // 模拟网络断开/后端重启触发 onerror → onDisconnect
    capturedDisconnect!()
    expect(state.phase).toBe('error')
    expect(isBusy()).toBe(false)
  })

  it('reset 清空所有字段', async () => {
    vi.mocked(client.uploadOne).mockResolvedValue({ id: 'a' })
    const { state, start, reset } = useBatch()
    await start([new File([], 'x.png')], false, 0.35, 0.9)
    reset()
    expect(state.phase).toBe('idle')
    expect(state.total).toBe(0)
    expect(state.items).toEqual([])
  })
})
