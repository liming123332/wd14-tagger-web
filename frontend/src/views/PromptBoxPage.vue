<script setup lang="ts">
import { ref, computed, onMounted, watch, h } from 'vue'
import {
  NSpace, NCard, NButton, NInput, NInputNumber, NDynamicTags, NUpload,
  NSelect, NTag, NGrid, NGridItem, NImage, NEmpty, useMessage,
} from 'naive-ui'
import {
  splitPrompt, analyzePromptbox, savePromptbox, promptboxWorkspaceImageUrl,
} from '../api/client'
import { useTagger } from '../composables/useTagger'

// 「提示词收藏」工作台（图库网格风格）：上传图片反推 → 工作区网格 → 点选拆分编辑 → 另存收藏。
// 反推图落 promptbox workspace（与图库隔离）；也保留「粘贴提示词拆分」入口（无图项）。

const msg = useMessage()
const tagger = useTagger()

const ORDER = ['quality', 'head', 'clothing', 'view', 'action', 'scene'] as const
const TITLES: Record<string, string> = {
  quality: '质量', head: '头部', clothing: '服装', view: '视角', action: '动作', scene: '场景', extras: '未归类',
}

// 工作区项：上传反推（有 local_id/thumb）或粘贴拆分（无图）。统一结构。
interface WorkspaceItem {
  local_id: string
  original: string
  thumb: string
  categories: Record<string, string[]>
  extras: string[]
  raw_prompt: string
  // 反推元数据（粘贴项无）：另存为收藏时携带，供编辑页重新反推/重分类
  model?: string
  gen_threshold?: number
  char_threshold?: number
  raw_tags?: Record<string, number>
}

const items = ref<WorkspaceItem[]>([])
const selectedIdx = ref(0)
const selected = computed(() => items.value[selectedIdx.value])

const title = ref('')
const pasteText = ref('')
const analyzing = ref(false)
const splitting = ref(false)

// 模型选择（独立 localModel，复用 useTagger；与上传页/详情页同款 renderTaggerLabel）
const localModel = ref('wd14')
const taggerOptions = computed(() => tagger.state.taggers.map(t => ({
  label: t.label, value: t.key, downloaded: t.downloaded,
})))
function renderTaggerLabel(option: any) {
  return h('span', { style: 'display:inline-flex;align-items:center;gap:6px' }, [
    option.label as any,
    option.downloaded
      ? h(NTag, { type: 'success', size: 'small', bordered: false }, { default: () => '已下载' })
      : h(NTag, { size: 'small', bordered: false }, { default: () => '未下载' }),
  ])
}
const modelDownloaded = computed(() => tagger.isDownloaded(localModel.value))
onMounted(() => { tagger.refresh() })
async function doDownload() {
  try { await tagger.download(localModel.value); msg.success('下载完成') }
  catch (e: any) { msg.error('下载失败：' + e.message) }
}

const genTh = ref(0.35)
const charTh = ref(0.9)
const isCl = computed(() => localModel.value === 'cl_tagger')
const charLabel = computed(() => isCl.value ? '角色名称识别阈值（仅 cl_tagger 生效）' : '角色阈值')
// cl_tagger 默认 0.6，用户切换模型时自适应（与 UploadPage 一致）
let modelChangeFromInit = false
watch(localModel, (m) => {
  if (modelChangeFromInit) { modelChangeFromInit = false; return }
  charTh.value = m === 'cl_tagger' ? 0.6 : 0.9
})

function emptyCats(): Record<string, string[]> {
  return Object.fromEntries(ORDER.map(k => [k, [] as string[]]))
}

// 上传反推
const fileList = ref<any[]>([])
function onUploadChange(opts: any) {
  const files = (opts.fileList || []).map((f: any) => f.file).filter(Boolean)
  if (files.length) doAnalyze(files)
}
async function doAnalyze(files: File[]) {
  if (!modelDownloaded.value) { msg.warning('当前模型未下载，请先下载'); return }
  analyzing.value = true
  try {
    const res = await analyzePromptbox(files, localModel.value, genTh.value, charTh.value)
    const start = items.value.length
    items.value = [...items.value, ...res.items.map(it => ({
      local_id: it.local_id, original: it.original, thumb: it.thumb,
      categories: { ...emptyCats(), ...it.categories },
      extras: [...it.extras], raw_prompt: it.raw_prompt,
      model: it.model, gen_threshold: genTh.value, char_threshold: charTh.value,
      raw_tags: it.raw_tags,
    }))]
    selectedIdx.value = start  // 选中本批第一张
    fileList.value = []
    msg.success(`反推完成 ${res.items.length} 张`)
  } catch (e: any) { msg.error('反推失败：' + e.message) }
  finally { analyzing.value = false }
}

// 粘贴拆分（无图工作区项）
async function doPasteSplit() {
  if (!pasteText.value.trim()) { msg.warning('请先输入提示词'); return }
  splitting.value = true
  try {
    const res = await splitPrompt(pasteText.value)
    items.value = [...items.value, {
      local_id: '', original: '', thumb: '',
      categories: { ...emptyCats(), ...res.categories },
      extras: [...res.extras], raw_prompt: pasteText.value,
    }]
    selectedIdx.value = items.value.length - 1
    msg.success('已拆分')
  } catch (e: any) { msg.error('拆分失败：' + e.message) }
  finally { splitting.value = false }
}

// 选中项分类编辑（直接改 items[idx]，ref 深度响应式）
function setCat(key: string, val: string[]) {
  const it = items.value[selectedIdx.value]
  if (it) it.categories[key] = val
}
function setExtras(val: string[]) {
  const it = items.value[selectedIdx.value]
  if (it) it.extras = val
}

const fullPrompt = computed(() => {
  const it = selected.value
  if (!it) return ''
  return [...ORDER.map(k => it.categories[k] || []).flat(), ...it.extras].filter(Boolean).join(', ')
})
async function copyPrompt() {
  if (!fullPrompt.value) { msg.warning('暂无提示词'); return }
  try { await navigator.clipboard.writeText(fullPrompt.value); msg.success('已复制完整 prompt') }
  catch { msg.error('复制失败') }
}

// 工作区图转 File：fetch workspace 原图 → blob → File，作为收藏示例图上传（复用现有 savePromptbox）
async function workspaceToFile(it: WorkspaceItem): Promise<File | null> {
  if (!it.local_id || !it.original) return null
  try {
    const r = await fetch(promptboxWorkspaceImageUrl(it.local_id, it.original))
    const blob = await r.blob()
    const ext = it.original.includes('.') ? it.original.slice(it.original.lastIndexOf('.')) : '.png'
    return new File([blob], 'example' + ext, { type: blob.type || 'image/png' })
  } catch { return null }
}

async function saveAsCollection() {
  const it = selected.value
  if (!it) { msg.warning('请先上传反推或粘贴拆分'); return }
  const fd = new FormData()
  fd.append('title', title.value)
  fd.append('raw_prompt', it.raw_prompt)
  fd.append('categories', JSON.stringify(it.categories))
  fd.append('extras', JSON.stringify(it.extras))
  // 携带反推元数据，供编辑页重新反推/重分类（粘贴项回退到当前工具栏值/空）
  fd.append('model', it.model || localModel.value)
  fd.append('gen_threshold', String(it.gen_threshold ?? genTh.value))
  fd.append('char_threshold', String(it.char_threshold ?? charTh.value))
  fd.append('raw_tags', JSON.stringify(it.raw_tags || {}))
  const file = await workspaceToFile(it)
  if (file) fd.append('files', file)
  try {
    await savePromptbox(fd)
    msg.success('已保存到收藏列表')
    title.value = ''
  } catch (e: any) { msg.error('保存失败：' + e.message) }
}

function selectItem(idx: number) { selectedIdx.value = idx }
function removeItem(idx: number) {
  items.value.splice(idx, 1)
  if (selectedIdx.value >= items.value.length) selectedIdx.value = Math.max(0, items.value.length - 1)
}
</script>

<template>
  <n-space vertical>
    <!-- 工具栏：上传反推 + 模型/阈值 + 粘贴 -->
    <n-card title="上传图片反推">
      <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:10px">
        <n-upload multiple :default-upload="false" :show-file-list="false"
                  v-model:file-list="fileList" @change="onUploadChange" accept="image/*">
          <n-button :loading="analyzing" type="primary">选择图片反推（可多选）</n-button>
        </n-upload>
        <span style="font-size:13px">反推模型</span>
        <n-select :value="localModel" :options="taggerOptions" :render-label="renderTaggerLabel"
                  @update:value="(v: string) => localModel = v" size="small" style="max-width:240px" />
        <div v-if="!modelDownloaded" style="display:flex;align-items:center;gap:6px">
          <span style="font-size:12px;color:#d03050">未下载</span>
          <n-button size="tiny" :loading="tagger.state.downloading === localModel" @click="doDownload">下载</n-button>
        </div>
      </div>
      <n-space>
        <div>通用阈值 <n-input-number v-model:value="genTh" :step="0.05" :min="0" :max="1" size="small" style="width:96px" /></div>
        <div>{{ charLabel }} <n-input-number v-model:value="charTh" :step="0.05" :min="0" :max="1" size="small" style="width:96px" /></div>
      </n-space>
      <div style="margin-top:12px">
        <n-input v-model:value="pasteText" type="textarea" :rows="2" placeholder="或粘贴提示词，逗号或换行分隔" />
        <n-button style="margin-top:8px" :loading="splitting" @click="doPasteSplit">粘贴拆分</n-button>
      </div>
    </n-card>

    <!-- 工作区网格 -->
    <div v-if="items.length">
      <div style="font-size:13px;margin-bottom:8px">工作区（点击选中以编辑/保存，共 {{ items.length }} 项）</div>
      <n-grid cols="2 600:3 900:5 1200:6" :x-gap="12" :y-gap="12">
        <n-grid-item v-for="(it, idx) in items" :key="it.local_id || ('paste-' + idx)">
          <div :class="['ws-card', { selected: idx === selectedIdx }]" @click="selectItem(idx)">
            <n-card size="small" hoverable>
              <div v-if="it.thumb" class="thumb">
                <n-image :src="promptboxWorkspaceImageUrl(it.local_id, it.thumb)"
                         object-fit="contain" preview-disabled />
              </div>
              <div v-else class="thumb placeholder">粘贴项</div>
              <div class="prompt">{{ it.raw_prompt || '(空)' }}</div>
              <n-button size="tiny" block @click.stop="removeItem(idx)">移除</n-button>
            </n-card>
          </div>
        </n-grid-item>
      </n-grid>
    </div>
    <n-empty v-else description="上传图片反推，或粘贴提示词拆分" />

    <!-- 选中项拆分编辑 -->
    <n-card v-if="selected" title="拆分编辑（选中项）">
      <div v-for="k in [...ORDER, 'extras']" :key="k" style="margin-top:8px">
        <div style="font-size:13px;margin-bottom:2px">{{ TITLES[k] }}</div>
        <n-dynamic-tags v-if="k !== 'extras'" :value="selected.categories[k] || []"
                        @update:value="(v: string[]) => setCat(k, v)" />
        <n-dynamic-tags v-else :value="selected.extras" @update:value="(v: string[]) => setExtras(v)" />
      </div>
      <div style="margin-top:12px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">
        <n-input v-model:value="title" placeholder="收藏标题（可选）" style="max-width:240px" />
        <n-button size="small" @click="copyPrompt">复制完整 prompt</n-button>
        <n-button size="small" type="primary" @click="saveAsCollection">另存为收藏</n-button>
      </div>
    </n-card>
  </n-space>
</template>

<style scoped>
.ws-card { cursor: pointer; border-radius: 6px; transition: outline 0.1s }
.ws-card.selected { outline: 2px solid #18a058; outline-offset: 2px }
.thumb { width: 100%; height: 160px; overflow: hidden }
.thumb.placeholder {
  display: flex; align-items: center; justify-content: center;
  color: #999; background: #f5f5f5; font-size: 13px;
}
.thumb :deep(.n-image) { display: block; width: 100%; height: 160px }
.thumb :deep(.n-image img) { width: 100%; height: 100%; object-fit: contain; display: block }
.prompt {
  font-size: 11px; color: #666; margin-top: 4px; margin-bottom: 4px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
</style>
