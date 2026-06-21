export function buildPrompt(meta: any): string {
  const order = ['quality', 'head', 'clothing', 'view', 'action', 'scene']
  // 未归类 extras 拼在末尾：详情页 TagEditor 的 extras 与各分类同构（{tags, phrase, user_edited}），
  // 拖拽到各类为「复制」不移除，故 extras 内标签仍需进入完整 prompt（与 PromptBoxPage fullPrompt 一致）。
  return [
    ...order.map(k => meta.categories?.[k]?.tags ?? []),
    ...(meta.extras?.tags ?? []),
  ].flat().filter(Boolean).join(', ')
}

export function parsePhrase(phrase: string): string[] {
  const s = (phrase || '').trim()
  if (!s) return []
  if (!s.includes(',')) return [s]
  return s.split(',').map(p => p.trim()).filter(Boolean)
}

// 角色/艺术家详情页用：权威 locked_tags（trigger+core_tags / 画师 tag）始终前置、不可移除。
// 锁定标签来自后端只读数据，覆盖层编辑绝不触碰；拼接时去空串。
export function buildPromptWithLocked(meta: any, lockedTags: string[] = []): string {
  const head = (lockedTags || []).filter(Boolean).join(', ')
  const base = buildPrompt(meta)
  return [head, base].filter(Boolean).join(', ')
}
