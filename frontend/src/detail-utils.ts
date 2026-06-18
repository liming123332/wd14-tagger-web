export function buildPrompt(meta: any): string {
  const order = ['quality', 'head', 'clothing', 'view', 'action', 'scene']
  return order.map(k => meta.categories?.[k]?.tags ?? []).flat().filter(Boolean).join(', ')
}

export function parsePhrase(phrase: string): string[] {
  const s = (phrase || '').trim()
  if (!s) return []
  if (!s.includes(',')) return [s]
  return s.split(',').map(p => p.trim()).filter(Boolean)
}
