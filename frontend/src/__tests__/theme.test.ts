import { describe, it, expect } from 'vitest'
import { lightOverrides, darkOverrides } from '../styles/theme'

describe('theme overrides', () => {
  it('主色紫蓝 #6366f1，深浅一致', () => {
    expect(lightOverrides.common?.primaryColor).toBe('#6366f1')
    expect(darkOverrides.common?.primaryColor).toBe('#6366f1')
  })
  it('深色底 #15171c / 卡片 #1c1f26；浅色底 #fafafa / 卡片 #ffffff', () => {
    expect(darkOverrides.common?.bodyColor).toBe('#15171c')
    expect(darkOverrides.common?.cardColor).toBe('#1c1f26')
    expect(lightOverrides.common?.bodyColor).toBe('#fafafa')
    expect(lightOverrides.common?.cardColor).toBe('#ffffff')
  })
  it('字体栈含 Microsoft YaHei', () => {
    expect(lightOverrides.common?.fontFamily).toContain('Microsoft YaHei')
  })
  it('卡片圆角 10px，按钮 6px', () => {
    expect(lightOverrides.Card?.borderRadius).toBe('10px')
    expect(lightOverrides.Button?.borderRadiusSmall).toBe('6px')
  })
})
