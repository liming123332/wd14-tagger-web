const base = ''

// ===== 类型 =====
export interface CfCategoryView { tags: string[]; phrase: string; user_edited: boolean }
export interface CfListItem {
  entry_key: string; source: string; name: string | null; series: string | null
  favorite: boolean
  // 角色
  trigger?: string; core_tags?: string; thumb_url?: string; image_url?: string
  // 艺术家
  tag?: string; thumb1_url?: string; thumb2_url?: string
}
export interface CfSaveBody {
  categories: Record<string, CfCategoryView>
  extras: CfCategoryView
  custom_tags: string[]
}
export interface CfDetail extends CfListItem {
  locked_tags: string[]
  categories: Record<string, CfCategoryView>
  extras: CfCategoryView
  custom_tags: string[]
  model: string; gen_threshold: number; char_threshold: number
  image_override: string | null
}

// entry_key = "{kind}:{source}:{key}"。key 可能含冒号（罕见），故只切前两段。
export function parseEntryKey(ek: string): { kind: string; source: string; key: string } {
  const parts = ek.split(':')
  return { kind: parts[0], source: parts[1], key: parts.slice(2).join(':') }
}

export function cfAssetUrl(kind: string, source: string, key: string, which: string): string {
  // 用 encodeURIComponent 与 cfQuery 统一：URLSearchParams 会把空格编成 + 并转义括号，与后端/测试预期不符
  const q = `kind=${encodeURIComponent(kind)}&source=${encodeURIComponent(source)}&key=${encodeURIComponent(key)}&which=${encodeURIComponent(which)}`
  return `${base}/api/cf/asset?${q}`
}

function cfQuery(source: string, key: string): string {
  return `source=${encodeURIComponent(source)}&key=${encodeURIComponent(key)}`
}

// ===== 角色 =====
export async function searchCharacters(
  query: string, source: string, series?: string, page = 1, size = 50,
): Promise<{ items: CfListItem[]; total: number }> {
  const q = new URLSearchParams({ query, source, page: String(page), size: String(size) })
  if (series) q.set('series', series)
  return fetch(`${base}/api/cf/characters?${q}`).then(r => r.json())
}

export async function listCharacterSeries(source: string): Promise<{ series: string; count: number }[]> {
  return fetch(`${base}/api/cf/characters/series?source=${encodeURIComponent(source)}`).then(r => r.json())
}

export async function getCharacter(source: string, key: string): Promise<CfDetail> {
  return fetch(`${base}/api/cf/character?${cfQuery(source, key)}`).then(r => r.json())
}

export async function tagCharacter(source: string, key: string, gen_th = 0.35, char_th = 0.9, model = 'wd14'): Promise<CfDetail> {
  return fetch(`${base}/api/cf/character/tag?${cfQuery(source, key)}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model, gen_th, char_th, use_char: true }),
  }).then(r => r.json())
}

export async function reclassifyCharacter(source: string, key: string, keep: Record<string, string[]>): Promise<CfDetail> {
  return fetch(`${base}/api/cf/character/reclassify?${cfQuery(source, key)}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keep }),
  }).then(r => r.json())
}

export async function saveCharacter(source: string, key: string, body: CfSaveBody): Promise<CfDetail> {
  return fetch(`${base}/api/cf/character?${cfQuery(source, key)}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),  // 只含 categories/extras/custom_tags，无 locked_tags
  }).then(r => r.json())
}

export async function uploadCharacterImage(source: string, key: string, file: File): Promise<{ image_override: string }> {
  const fd = new FormData()
  fd.append('file', file)
  return fetch(`${base}/api/cf/character/image?${cfQuery(source, key)}`, { method: 'POST', body: fd }).then(r => r.json())
}

export async function toggleCharacterFavorite(source: string, key: string): Promise<{ favorite: boolean }> {
  return fetch(`${base}/api/cf/character/favorite?${cfQuery(source, key)}`, { method: 'POST' }).then(r => r.json())
}

// ===== 艺术家（同构，路径单数 artist / 复数 artists） =====
export async function searchArtists(
  query: string, source: string, page = 1, size = 50,
): Promise<{ items: CfListItem[]; total: number }> {
  const q = new URLSearchParams({ query, source, page: String(page), size: String(size) })
  return fetch(`${base}/api/cf/artists?${q}`).then(r => r.json())
}

export async function getArtist(source: string, key: string): Promise<CfDetail> {
  return fetch(`${base}/api/cf/artist?${cfQuery(source, key)}`).then(r => r.json())
}

export async function tagArtist(source: string, key: string, gen_th = 0.35, char_th = 0.9, model = 'wd14'): Promise<CfDetail> {
  return fetch(`${base}/api/cf/artist/tag?${cfQuery(source, key)}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model, gen_th, char_th, use_char: true }),
  }).then(r => r.json())
}

export async function reclassifyArtist(source: string, key: string, keep: Record<string, string[]>): Promise<CfDetail> {
  return fetch(`${base}/api/cf/artist/reclassify?${cfQuery(source, key)}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keep }),
  }).then(r => r.json())
}

export async function saveArtist(source: string, key: string, body: CfSaveBody): Promise<CfDetail> {
  return fetch(`${base}/api/cf/artist?${cfQuery(source, key)}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(r => r.json())
}

export async function uploadArtistImage(source: string, key: string, file: File): Promise<{ image_override: string }> {
  const fd = new FormData()
  fd.append('file', file)
  return fetch(`${base}/api/cf/artist/image?${cfQuery(source, key)}`, { method: 'POST', body: fd }).then(r => r.json())
}

export async function toggleArtistFavorite(source: string, key: string): Promise<{ favorite: boolean }> {
  return fetch(`${base}/api/cf/artist/favorite?${cfQuery(source, key)}`, { method: 'POST' }).then(r => r.json())
}

// ===== 收藏 / 最近 / 随机（消费 P1 Task 11 只读端点）=====
export async function listCfFavorites(kind: 'char' | 'artist'): Promise<{ items: CfListItem[] }> {
  return fetch(`${base}/api/cf/favorites?kind=${encodeURIComponent(kind)}`).then(r => r.json())
}

export async function listCfRecent(kind: 'char' | 'artist', limit = 50): Promise<{ items: CfListItem[] }> {
  const q = new URLSearchParams({ kind, limit: String(limit) })
  return fetch(`${base}/api/cf/recent?${q}`).then(r => r.json())
}

export async function randomCf(type: 'characters' | 'artists', source: string, size = 24): Promise<{ items: CfListItem[] }> {
  const q = new URLSearchParams({ type, source, size: String(size) })
  return fetch(`${base}/api/cf/random?${q}`).then(r => r.json())
}
