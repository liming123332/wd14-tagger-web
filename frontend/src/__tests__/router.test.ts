import { describe, it, expect } from 'vitest'
import { router } from '../router'

describe('router routes', () => {
  it('注册角色与艺术家路由', () => {
    const paths = router.getRoutes().map(r => r.path)
    expect(paths).toContain('/characters')
    expect(paths).toContain('/characters/:source/:key')
    expect(paths).toContain('/artists')
    expect(paths).toContain('/artists/:source/:key')
  })
})
