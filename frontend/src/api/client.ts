const base = ''

export async function uploadImages(files: File[]): Promise<{ ids: string[] }> {
  const fd = new FormData()
  for (const f of files) fd.append('files', f)
  const r = await fetch(`${base}/api/images`, { method: 'POST', body: fd })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function uploadOne(file: File): Promise<{ id: string }> {
  const fd = new FormData()
  fd.append('files', file)
  const r = await fetch(`${base}/api/images`, { method: 'POST', body: fd })
  if (!r.ok) throw new Error(await r.text())
  const data = await r.json()
  return { id: data.ids[0] }
}

export async function listImages(page = 1, size = 24) {
  return fetch(`${base}/api/images?page=${page}&size=${size}`).then(r => r.json())
}

export async function getMeta(id: string) {
  return fetch(`${base}/api/images/${id}`).then(r => r.json())
}

export async function saveMeta(id: string, meta: any) {
  return fetch(`${base}/api/images/${id}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(meta),
  }).then(r => r.json())
}

export async function tagImage(id: string, gen_th = 0.35, char_th = 0.9) {
  return fetch(`${base}/api/images/${id}/tag`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ gen_th, char_th, use_char: true }),
  }).then(r => r.json())
}

export async function reclassify(id: string) {
  return fetch(`${base}/api/images/${id}/reclassify`, { method: 'POST' }).then(r => r.json())
}

export async function deleteImage(id: string) {
  return fetch(`${base}/api/images/${id}`, { method: 'DELETE' }).then(r => r.json())
}

export async function startBatch(ids: string[], gen_th = 0.35, char_th = 0.9) {
  return fetch(`${base}/api/batch/tag`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids, gen_th, char_th }),
  }).then(r => r.json())
}

export function subscribeBatch(batchId: string, onEvent: (e: any) => void) {
  const es = new EventSource(`${base}/api/batch/${batchId}/events`)
  es.onmessage = (m) => {
    const data = JSON.parse(m.data)
    onEvent(data)
    if (data.type === 'done') es.close()
  }
  es.onerror = () => es.close()
  return es
}

export function fileUrl(id: string, name: string) {
  return `${base}/api/images/${id}/file/${name}`
}

