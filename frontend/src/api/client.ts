const base = ''

export async function uploadImages(files: File[], tags?: string[]): Promise<{ ids: string[] }> {
  const fd = new FormData()
  for (const f of files) fd.append('files', f)
  for (const t of tags || []) fd.append('tags', t)
  const r = await fetch(`${base}/api/images`, { method: 'POST', body: fd })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function uploadOne(file: File, tags?: string[]): Promise<{ id: string }> {
  const fd = new FormData()
  fd.append('files', file)
  for (const t of tags || []) fd.append('tags', t)
  const r = await fetch(`${base}/api/images`, { method: 'POST', body: fd })
  if (!r.ok) throw new Error(await r.text())
  const data = await r.json()
  return { id: data.ids[0] }
}

export async function listImages(page = 1, size = 24, date?: string, tags?: string[], prompt?: string) {
  const q = new URLSearchParams({ page: String(page), size: String(size) })
  if (date) q.set('date', date)
  for (const t of tags || []) q.append('tags', t)
  // prompt 整串按逗号/空格拆词，每个词一个 prompt 参数（后端交集匹配）
  for (const w of (prompt || '').split(/[,\s]+/).filter(Boolean)) q.append('prompt', w)
  return fetch(`${base}/api/images?${q}`).then(r => r.json())
}

export async function listTags(): Promise<Record<string, number>> {
  return fetch(`${base}/api/images/tags`).then(r => r.json())
}

// 把 tags 合并进该分类的 exact 词表并 reload 分类器（下次反推即归类）
export async function applyCategoryRules(category: string, tags: string[]) {
  return fetch(`${base}/api/config/rules/${category}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tags }),
  }).then(r => r.json())
}

export async function randomImages(size = 24) {
  return fetch(`${base}/api/images?size=${size}&random=true`).then(r => r.json())
}

export async function getMeta(id: string) {
  return fetch(`${base}/api/images/${id}`).then(r => r.json())
}

export async function saveMeta(id: string, meta: any) {
  return fetch(`${base}/api/images/${id}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(meta),
  }).then(r => r.json())
}

export async function tagImage(id: string, gen_th = 0.35, char_th = 0.9, model = 'wd14') {
  return fetch(`${base}/api/images/${id}/tag`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ gen_th, char_th, use_char: true, model }),
  }).then(r => r.json())
}

export async function reclassify(id: string) {
  return fetch(`${base}/api/images/${id}/reclassify`, { method: 'POST' }).then(r => r.json())
}

export async function deleteImage(id: string) {
  return fetch(`${base}/api/images/${id}`, { method: 'DELETE' }).then(r => r.json())
}

export async function startBatch(ids: string[], gen_th = 0.35, char_th = 0.9, model = 'wd14') {
  return fetch(`${base}/api/batch/tag`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids, gen_th, char_th, model }),
  }).then(r => r.json())
}

export function subscribeBatch(
  batchId: string,
  onEvent: (e: any) => void,
  onDisconnect?: () => void,
) {
  const es = new EventSource(`${base}/api/batch/${batchId}/events`)
  es.onmessage = (m) => {
    const data = JSON.parse(m.data)
    onEvent(data)
    if (data.type === 'done') es.close()
  }
  es.onerror = () => { es.close(); onDisconnect?.() }
  return es
}

export function fileUrl(id: string, name: string) {
  return `${base}/api/images/${id}/file/${name}`
}

export interface TaggerInfo { key: string; label: string; downloaded: boolean }

export async function listTaggers(): Promise<TaggerInfo[]> {
  return fetch(`${base}/api/taggers`).then(r => r.json())
}

export async function downloadTagger(key: string): Promise<{ key: string; downloaded: boolean }> {
  return fetch(`${base}/api/taggers/${key}/download`, { method: 'POST' }).then(r => r.json())
}

export interface PromptboxItem {
  id: string
  title: string
  raw_prompt: string
  categories: Record<string, string[]>
  extras: string[]
  image_names: string[]
  created_at: string
  updated_at: string
}

export async function splitPrompt(text: string): Promise<{ categories: Record<string, string[]>; extras: string[] }> {
  return fetch(`${base}/api/promptbox/split`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  }).then(r => r.json())
}

export async function listPromptbox(): Promise<PromptboxItem[]> {
  return fetch(`${base}/api/promptbox`).then(r => r.json())
}

export async function savePromptbox(fd: FormData): Promise<PromptboxItem> {
  const r = await fetch(`${base}/api/promptbox`, { method: 'POST', body: fd })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function updatePromptbox(id: string, fd: FormData): Promise<PromptboxItem> {
  const r = await fetch(`${base}/api/promptbox/${id}`, { method: 'PUT', body: fd })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function deletePromptbox(id: string) {
  return fetch(`${base}/api/promptbox/${id}`, { method: 'DELETE' }).then(r => r.json())
}

export function promptboxImageUrl(id: string, name: string) {
  return `${base}/api/promptbox/${id}/image/${name}`
}

export interface AnalyzedItem {
  local_id: string
  original: string
  thumb: string
  width: number
  height: number
  model: string
  categories: Record<string, string[]>
  extras: string[]
  raw_prompt: string
}

// 提示词收藏页「上传反推」：图落 promptbox workspace（不进图库），返回每图分类结果。
// raw_prompt 含全部 6 类 + extras，供工作区卡片预览/复制。
export async function analyzePromptbox(
  files: File[], model: string, genTh: number, charTh: number,
): Promise<{ items: AnalyzedItem[] }> {
  const fd = new FormData()
  for (const f of files) fd.append('files', f)
  fd.append('model', model)
  fd.append('gen_th', String(genTh))
  fd.append('char_th', String(charTh))
  const r = await fetch(`${base}/api/promptbox/analyze`, { method: 'POST', body: fd })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export function promptboxWorkspaceImageUrl(localId: string, name: string) {
  return `${base}/api/promptbox/workspace/${localId}/image/${name}`
}

