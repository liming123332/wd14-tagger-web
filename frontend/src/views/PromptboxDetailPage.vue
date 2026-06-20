<script setup lang="ts">
import { ref, computed, watch, onMounted, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NSpace, NButton, NRadioGroup, NRadioButton, NImage, NCard,
  NInputNumber, NInput, useMessage, NPopconfirm, NSelect, NTag, NEmpty, NUpload,
} from 'naive-ui'
import TagEditor from '../components/TagEditor.vue'
import {
  getPromptbox, updatePromptbox, deletePromptbox,
  tagPromptbox, reclassifyPromptbox, promptboxImageUrl,
  applyCategoryRules, type PromptboxItem,
} from '../api/client'
import { useTagger } from '../composables/useTagger'
import { IconPlus } from '../components/icons'

// 收藏编辑页：复用图库 DetailPage 布局 + TagEditor/applyCategoryRules/useTagger 件，
// 适配 promptbox 数据结构。promptbox 的 categories 是 string[]，这里加载时包成
// {tags,phrase,user_edited}（TagEditor 要的形状），保存时拆回 string[]。
// 重新反推/重分类复刻图库语义：raw_tags 来自反推；本次手改的类(handEdited)作为 keep
// 传给 reclassify 跳过，等价于图库的 user_edited（但不持久化，作用域为当前编辑会话）。

const tagger = useTagger()
const route = useRoute(); const router = useRouter(); const msg = useMessage()
const id = computed(() => route.params.id as string)

const ORDER = ['quality', 'head', 'clothing', 'view', 'action', 'scene'] as const
const KEY_TITLES: [string, string, string][] = [
  ['head', '角色头部', '#4CAF50'], ['clothing', '服装', '#2196F3'],
  ['view', '视角构图', '#9C27B0'], ['action', '动作', '#FF9800'],
  ['scene', '场景', '#795548'], ['quality', '质量词（预设）', '#607D8B'],
]

interface CatView { tags: string[]; phrase: string; user_edited: boolean }
const emptyCat = (): CatView => ({ tags: [], phrase: '', user_edited: false })

const item = ref<PromptboxItem | null>(null)
const catsView = ref<Record<string, CatView>>(Object.fromEntries(ORDER.map(k => [k, emptyCat()])))
const extrasView = ref<CatView>(emptyCat())
// 本次编辑会话内手改过的类（用于 reclassify 的 keep），不持久化
const handEdited = ref<Set<string>>(new Set())

const mode = ref<'tags' | 'phrase'>('tags')
const dirty = ref(false)
const genTh = ref(0.35)
const charTh = ref(0.9)
const localModel = ref('')

const taggerOptions = computed(() => tagger.state.taggers.map(t => ({
  label: t.label, value: t.key, downloaded: t.downloaded,
})))
// naive-ui NSelect 的 render-label 是 prop（render function），非插槽
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
const charLabel = computed(() => localModel.value === 'cl_tagger' ? '角色名称识别阈值（仅 cl_tagger 生效）' : '角色')
let modelChangeFromLoad = false
watch(localModel, (m) => {
  if (modelChangeFromLoad) { modelChangeFromLoad = false; return }
  if (m === 'cl_tagger_v2') { genTh.value = 0.55; charTh.value = 0.55 }
  else { charTh.value = m === 'cl_tagger' ? 0.6 : 0.9 }
})

function fromItem(it: PromptboxItem) {
  item.value = it
  const v: Record<string, CatView> = {}
  for (const k of ORDER) {
    const tags = it.categories[k] || []
    v[k] = { tags: [...tags], phrase: tags.join(', '), user_edited: false }
  }
  catsView.value = v
  extrasView.value = { tags: [...it.extras], phrase: it.extras.join(', '), user_edited: false }
  handEdited.value = new Set()
  // v2 单阈值运营（文档推荐 0.55）：历史项可能记的是旧 wd 默认值，打开时强制刷成 0.55
  // ——仅改显示，item 不落库；点「重新反推」才以 0.55 写回。其它模型沿用记录值。
  if (it.model === 'cl_tagger_v2') {
    genTh.value = 0.55
    charTh.value = 0.55
  } else {
    genTh.value = it.gen_threshold
    charTh.value = it.char_threshold
  }
  modelChangeFromLoad = true
  localModel.value = it.model
}

async function load() {
  const cur = id.value
  try {
    const it = await getPromptbox(cur)
    if (cur !== id.value) return  // 已切到其它收藏，丢弃旧结果防竞态
    fromItem(it); dirty.value = false
  } catch (e: any) { msg.error('加载失败：' + e.message) }
}
watch(id, load, { immediate: true })

function setCat(key: string, val: CatView) {
  catsView.value[key] = val; dirty.value = true
  if (val.user_edited) handEdited.value.add(key)
}
function setExtras(val: CatView) { extrasView.value = val; dirty.value = true }

function onName(v: string) { if (item.value) { item.value.title = v; dirty.value = true } }

function applyPhrase(key: string, tags: string[]) {
  const next = { tags, phrase: tags.join(', '), user_edited: true }
  if (key === 'extras') setExtras(next); else setCat(key, next)
}

async function onApplyRule(key: string, title: string, tags: string[]) {
  if (!tags || !tags.length) { msg.warning('该分类暂无标签可应用'); return }
  try { await applyCategoryRules(key, tags); msg.success(`已加入「${title}」分类词表，下次反推自动归类`) }
  catch (e: any) { msg.error('应用失败：' + e.message) }
}

function toCatsOut(): Record<string, string[]> {
  const out: Record<string, string[]> = {}
  for (const k of ORDER) out[k] = catsView.value[k].tags
  return out
}

// PUT FormData：save（仅字段）与 uploadImage（字段+图）共用。
// files 走 update 端点的 new_image_data，后端只追加存图、不反推。
function buildFd(files?: File[]): FormData {
  const fd = new FormData()
  fd.append('title', item.value!.title)
  fd.append('raw_prompt', item.value!.raw_prompt)
  fd.append('categories', JSON.stringify(toCatsOut()))
  fd.append('extras', JSON.stringify(extrasView.value.tags))
  if (files) for (const f of files) fd.append('files', f, f.name)
  return fd
}

async function save() {
  if (!item.value) return
  try {
    const updated = await updatePromptbox(id.value, buildFd())
    fromItem(updated); dirty.value = false; msg.success('已保存')
  } catch (e: any) { msg.error('保存失败：' + e.message) }
}

// 上传示例图：update 带 files 追加存图，不自动反推（想反推手动点「重新反推」）。
async function uploadImage(file: File) {
  if (!item.value) return
  try {
    const updated = await updatePromptbox(id.value, buildFd([file]))
    fromItem(updated); msg.success('图片已上传（未自动反推）')
  } catch (e: any) { msg.error('上传失败：' + e.message) }
}
// NUpload custom-request 适配：取原生 File 调 uploadImage
function onUploadReq({ file }: any) {
  const f = (file as any)?.file as File | undefined
  if (f) uploadImage(f)
}

const hasImage = computed(() => !!item.value && item.value.image_names.length > 0)
const hasRawTags = computed(() => !!item.value && Object.keys(item.value.raw_tags || {}).length > 0)

async function reTag() {
  try {
    const updated = await tagPromptbox(id.value, genTh.value, charTh.value, localModel.value)
    fromItem(updated); msg.success('反推完成')
  } catch (e: any) { msg.error('反推失败：' + e.message) }
}
async function reClassify() {
  const keep: Record<string, string[]> = {}
  handEdited.value.forEach(k => { keep[k] = catsView.value[k].tags })
  try {
    const updated = await reclassifyPromptbox(id.value, keep)
    fromItem(updated); msg.success('重分类完成（跳过手改类）')
  } catch (e: any) { msg.error('重分类失败：' + e.message) }
}
async function del() {
  await deletePromptbox(id.value); msg.success('已删除'); router.push('/collections')
}

const fullPrompt = computed(() => {
  if (!item.value) return ''
  return [...ORDER.map(k => catsView.value[k]?.tags ?? []).flat(), ...extrasView.value.tags]
    .filter(Boolean).join(', ')
})
async function copyPrompt() {
  if (!fullPrompt.value) { msg.warning('暂无提示词'); return }
  try { await navigator.clipboard.writeText(fullPrompt.value); msg.success('已复制完整 prompt') }
  catch { msg.error('复制失败') }
}
</script>

<template>
  <div v-if="item" style="display:grid;grid-template-columns:minmax(280px,1fr) minmax(0,2fr);gap:16px">
    <div>
      <n-card>
        <div class="img-wrap">
          <n-image v-if="hasImage" :src="promptboxImageUrl(id, item.image_names[0])"
                   :preview-src="promptboxImageUrl(id, item.image_names[0])"
                   object-fit="contain" style="max-height:420px;width:100%;display:block" />
          <div v-else class="no-img">无图片（点下方「上传图片」或「重新反推」）</div>
        </div>
        <div style="font-size:12px;margin-top:8px">
          <div style="margin-bottom:4px">
            标题 <n-input :value="item.title" size="small" @update:value="onName" placeholder="收藏标题" style="width:240px" />
          </div>
          <div>{{ item.image_names.length }} 张示例图 · {{ item.model }}</div>
          <div style="margin-top:6px">
            <div style="font-size:13px;margin-bottom:4px">反推模型</div>
            <n-select :value="localModel" :options="taggerOptions" :render-label="renderTaggerLabel"
                      @update:value="(v: string) => localModel = v" size="small" style="max-width:260px" />
            <div v-if="!modelDownloaded" style="margin-top:4px;display:flex;align-items:center;gap:6px">
              <span style="font-size:12px;color:#d03050">{{ tagger.state.taggers.find(t=>t.key===localModel)?.label || localModel }} 未下载</span>
              <n-button size="tiny" :loading="tagger.state.downloading===localModel" @click="doDownload">下载</n-button>
            </div>
          </div>
          <!-- v2 单阈值不区分角色阈值：隐藏角色框（charTh 仍保留 0.55 传后端，被忽略） -->
          <div>通用 <n-input-number v-model:value="genTh" :step="0.05" :min="0" :max="1" size="small" style="width:96px" /><template v-if="localModel !== 'cl_tagger_v2'"> / {{ charLabel }} <n-input-number v-model:value="charTh" :step="0.05" :min="0" :max="1" size="small" style="width:96px" /></template></div>
        </div>
        <n-space vertical style="margin-top:8px">
          <n-upload :show-file-list="false" :max="1" accept="image/*" :custom-request="onUploadReq">
            <n-button size="small"><IconPlus/> 上传图片</n-button>
          </n-upload>
          <n-button size="small" :disabled="!hasImage" @click="reTag">重新反推</n-button>
          <n-button size="small" :disabled="!hasRawTags" @click="reClassify">重分类</n-button>
          <n-button size="small" @click="copyPrompt">复制完整 prompt</n-button>
          <n-popconfirm @positive-click="del"><template #trigger><n-button size="small" type="error">删除</n-button></template>确认删除？</n-popconfirm>
        </n-space>
      </n-card>
    </div>
    <div>
      <n-space align="center" style="margin-bottom:10px">
        <n-radio-group v-model:value="mode" size="small">
          <n-radio-button value="tags">标签</n-radio-button>
          <n-radio-button value="phrase">短句</n-radio-button>
        </n-radio-group>
        <n-button size="small" type="primary" :disabled="!dirty" @click="save">保存</n-button>
      </n-space>
      <TagEditor v-for="[key, title, color] in KEY_TITLES" :key="key" :title="title" :color="color"
                 :mode="mode" :category-key="key"
                 :model-value="catsView[key] || emptyCat()"
                 @update:modelValue="(v) => setCat(key, v)" @apply-phrase="(t) => applyPhrase(key, t)"
                 @apply-rule="(t) => onApplyRule(key, title, t)" />
      <TagEditor title="未归类 extras（拖到各类为复制，不会移除原标签）" color="#9E9E9E" :mode="mode"
                 category-key="extras"
                 :model-value="extrasView"
                 @update:modelValue="setExtras" @apply-phrase="(t) => applyPhrase('extras', t)" />
    </div>
  </div>
  <n-empty v-else description="加载中..." />
</template>

<style scoped>
/* promptbox 仅存原图（无图库 thumb 缩略图）。强制 n-image block + 100% 宽，
   并把 img 等比缩进 420px 框（max-height + object-fit:contain），避免大图溢出卡片。
   图库 DetailPage 靠 thumb 小图避免溢出；这里没有 thumb，故用 max-height 兜底，
   视觉与图库一致（图 contain 进 420px 框，点击仍预览原图）。 */
:deep(.n-image) { display: block; width: 100%; }
:deep(.n-image img) {
  max-width: 100%;
  max-height: 420px;
  width: auto;
  height: auto;
  object-fit: contain;
  display: block;
  margin: 0 auto;
}
.no-img {
  height: 200px; display: flex; align-items: center; justify-content: center;
  font-size: 13px; border-radius: 4px;
}
.img-wrap {
  border-radius: 10px;
  padding: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
