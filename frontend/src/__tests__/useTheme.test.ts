import { describe, it, expect, vi, beforeEach } from 'vitest'

function mockMatchMedia(dark: boolean) {
  const listeners: ((e: any) => void)[] = []
  vi.stubGlobal('matchMedia', vi.fn().mockImplementation(() => ({
    matches: dark,
    addEventListener: (_: string, cb: (e: any) => void) => listeners.push(cb),
    removeEventListener: () => {},
  })))
  return listeners
}

describe('useTheme', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.unstubAllGlobals()
    vi.resetModules()
  })

  it('默认 auto；系统亮→effective light', async () => {
    mockMatchMedia(false)
    const { useTheme } = await import('../composables/useTheme')
    const { mode, effective } = useTheme()
    expect(mode.value).toBe('auto')
    expect(effective.value).toBe('light')
  })

  it('auto + 系统暗→effective dark', async () => {
    mockMatchMedia(true)
    const { useTheme } = await import('../composables/useTheme')
    const { effective } = useTheme()
    expect(effective.value).toBe('dark')
  })

  it('setMode 写 localStorage', async () => {
    mockMatchMedia(false)
    const { useTheme } = await import('../composables/useTheme')
    const { setMode } = useTheme()
    setMode('dark')
    expect(localStorage.getItem('wd14.theme')).toBe('dark')
  })

  it('启动读 localStorage 覆盖默认', async () => {
    localStorage.setItem('wd14.theme', 'dark')
    mockMatchMedia(false)
    const { useTheme } = await import('../composables/useTheme')
    const { mode } = useTheme()
    expect(mode.value).toBe('dark')
  })
})
