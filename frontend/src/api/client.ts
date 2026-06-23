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

// 图库详情「替换图片」：覆盖原图+缩略图，保留 meta 标签（后端不自动反推）
export async function replaceImage(id: string, file: File) {
  const fd = new FormData()
  fd.append('file', file)
  const r = await fetch(`${base}/api/images/${id}/replace`, { method: 'POST', body: fd })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
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

// 路径打标：提交本地文件夹路径，后端展开图片反推并写同名 .txt，返回 job_id/total
export interface PathTagPayload {
  path: string
  model: string
  gen_th: number
  char_th: number
  use_char: boolean
  recursive: boolean
  on_conflict: 'overwrite' | 'skip'
}

export async function startPathTag(payload: PathTagPayload): Promise<{ job_id: string; total: number }> {
  const r = await fetch(`${base}/api/pathtag/start`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export function subscribePathTag(jobId: string, onEvent: (e: any) => void, onDisconnect?: () => void) {
  const es = new EventSource(`${base}/api/pathtag/${jobId}/events`)
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
  const r = await fetch(`${base}/api/taggers/${key}/download`, { method: 'POST' })
  if (!r.ok) {
    // 下载失败（如 gated 模型 401/403、网络中断）：把后端 detail 透传给前端提示
    let detail = ''
    try { detail = (await r.json()).detail || '' } catch { detail = await r.text() }
    throw new Error(detail || `HTTP ${r.status}`)
  }
  return r.json()
}

export interface DownloadProgress {
  active: boolean
  key: string
  file: string
  index: number
  total_files: number
  downloaded: number
  size: number
  done: boolean
  error: string
}

// 当前下载任务进度（前端轮询显示）
export async function getDownloadProgress(): Promise<DownloadProgress> {
  return fetch(`${base}/api/taggers/download-progress`).then(r => r.json())
}

// 卸载所有已加载模型（从内存/显存释放 ONNX session，不删文件；下次反推重新加载）
export async function unloadAllTaggers(): Promise<{ released: string[] }> {
  const r = await fetch(`${base}/api/taggers/unload-all`, { method: 'POST' })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
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
  model: string
  gen_threshold: number
  char_threshold: number
  raw_tags: Record<string, number>
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

export async function getPromptbox(id: string): Promise<PromptboxItem> {
  const r = await fetch(`${base}/api/promptbox/${id}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
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

// 提示词收藏详情「替换主图」：覆盖第一张示例图
export async function replacePromptboxImage(id: string, file: File): Promise<PromptboxItem> {
  const fd = new FormData()
  fd.append('file', file)
  const r = await fetch(`${base}/api/promptbox/${id}/replace-image`, { method: 'POST', body: fd })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
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
  raw_tags: Record<string, number>
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

export interface WorkspaceImageInfo {
  local_id: string; original: string; thumb: string; width: number; height: number
}
// 提示词收藏「粘贴拆分（可附图）」：只把图存到 workspace（不反推），返回 local_id/原图/缩略图。
export async function uploadPromptboxWorkspaceImage(
  files: File[],
): Promise<{ items: WorkspaceImageInfo[] }> {
  const fd = new FormData()
  for (const f of files) fd.append('files', f)
  const r = await fetch(`${base}/api/promptbox/workspace/image`, { method: 'POST', body: fd })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

// 收藏编辑页「重新反推」：读收藏示例图反推，返回更新后的 item（含新 raw_tags/categories）
export async function tagPromptbox(id: string, gen_th = 0.35, char_th = 0.9, model = 'wd14') {
  return fetch(`${base}/api/promptbox/${id}/tag`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ gen_th, char_th, use_char: true, model }),
  }).then(r => r.json())
}

// 收藏编辑页「重分类」：keep 里的类保留手改值（复刻图库 user_edited 语义），其余用 raw_tags 重算
export async function reclassifyPromptbox(id: string, keep: Record<string, string[]>) {
  return fetch(`${base}/api/promptbox/${id}/reclassify`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keep }),
  }).then(r => r.json())
}

// === 翻译（Hy-MT2，本地 GGUF 推理，不落地，每次现译）===
export async function translateStatus(): Promise<{ downloaded: boolean; loaded: boolean }> {
  return fetch(`${base}/api/translate/status`).then(r => r.json())
}

// 下载翻译模型：ensure_loaded 补全 GGUF + 加载；进度复用 getDownloadProgress（同 tagger）
export async function downloadTranslator(): Promise<{ downloaded: boolean }> {
  const r = await fetch(`${base}/api/translate/download`, { method: 'POST' })
  if (!r.ok) {
    let detail = ''
    try { detail = (await r.json()).detail || '' } catch { detail = await r.text() }
    throw new Error(detail || `HTTP ${r.status}`)
  }
  return r.json()
}

// 翻译一批标签（英文→中文）。409=未下载，前端编排先下载再重试
export async function translateTags(texts: string[], target?: string): Promise<{ results: string[] }> {
  const r = await fetch(`${base}/api/translate`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ texts, target }),
  })
  if (!r.ok) {
    let detail = ''
    try { detail = (await r.json()).detail || '' } catch { detail = await r.text() }
    throw new Error(detail || `HTTP ${r.status}`)
  }
  return r.json()
}

// 中文→英文标签（详情页中文添加用）：双马尾→twintails。409=未下载
export async function translateToTags(texts: string[]): Promise<{ results: string[] }> {
  const r = await fetch(`${base}/api/translate/to-tags`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ texts }),
  })
  if (!r.ok) {
    let detail = ''
    try { detail = (await r.json()).detail || '' } catch { detail = await r.text() }
    throw new Error(detail || `HTTP ${r.status}`)
  }
  return r.json()
}

// 卸载翻译模型 Llama（释放显存/RAM，不删 GGUF）
export async function unloadTranslator(): Promise<{ released: boolean }> {
  const r = await fetch(`${base}/api/translate/unload`, { method: 'POST' })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

