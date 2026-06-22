<script setup lang="ts">
import { ref, computed, watch, onMounted, h } from 'vue'
import { useRoute } from 'vue-router'
import {
  NSpace, NButton, NRadioGroup, NRadioButton, NImage, NCard,
  NInputNumber, NDynamicTags, NTag, NUpload, NSelect,
  useMessage,
} from 'naive-ui'
import TagEditor from '../components/TagEditor.vue'
import {
  getCharacter, tagCharacter, reclassifyCharacter, saveCharacter,
  uploadCharacterImage, toggleCharacterFavorite, refreshThumb, type CfDetail,
} from '../api/characterfinder'
import { useTagger } from '../composables/useTagger'
import { buildPromptWithLocked } from '../detail-utils'
import { IconPlus } from '../components/icons'

const tagger = useTagger()
const route = useRoute(); const msg = useMessage()
const source = computed(() => route.params.source as string)
const key = computed(() => route.params.key as string)

const KEY_TITLES: [string, string, string][] = [
  ['head', '角色头部', '#4CAF50'], ['clothing', '服装', '#2196F3'],
  ['view', '视角构图', '#9C27B0'], ['action', '动作', '#FF9800'],
  ['scene', '场景', '#795548'], ['quality', '质量词（预设）', '#607D8B'],
]

const detail = ref<CfDetail | null>(null)
const mode = ref<'tags' | 'phrase'>('tags')
const dirty = ref(false)
const genTh = ref(0.35); const charTh = ref(0.9)
const localModel = ref('')
const handEdited = ref<Set<string>>(new Set())
// 换图后强制刷新 <n-image>（asset URL 不变，内容变了）
const imgVersion = ref(0)

const taggerOptions = computed(() => tagger.state.taggers.map(t => ({ label: t.label, value: t.key, downloaded: t.downloaded })))
function renderTaggerLabel(option: any) {
  return h('span', { style: 'display:inline-flex;align-items:center;gap:6px' }, [
    option.label as any,
    option.downloaded ? h(NTag, { type: 'success', size: 'small', bordered: false }, { default: () => '已下载' })
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

function fromDetail(d: CfDetail) {
  detail.value = d; dirty.value = false; handEdited.value = new Set()
  if (d.model === 'cl_tagger_v2') { genTh.value = 0.55; charTh.value = 0.55 }
  else { genTh.value = d.gen_threshold; charTh.value = d.char_threshold }
  modelChangeFromLoad = true; localModel.value = d.model
}

async function load() {
  const s = source.value, k = key.value
  try {
    const d = await getCharacter(s, k)
    if (s !== source.value || k !== key.value) return  // 已切条目，丢弃旧结果防竞态
    fromDetail(d)
  } catch (e: any) { msg.error('加载失败：' + e.message) }
}
watch([source, key], load, { immediate: true })

// 后端 categories 已是 {k:{tags,phrase,user_edited}}，与 TagEditor modelValue 同构，直接改
function setCat(k: string, val: any) { detail.value!.categories[k] = val; dirty.value = true; if (val.user_edited) handEdited.value.add(k) }
function setExtras(val: any) { detail.value!.extras = val; dirty.value = true }
function onCustomTags(v: string[]) { detail.value!.custom_tags = v; dirty.value = true }
function applyPhrase(k: string, tags: string[]) {
  const next = { tags, phrase: tags.join(', '), user_edited: true }
  if (k === 'extras') setExtras(next); else setCat(k, next)
}

async function save() {
  if (!detail.value) return
  try {
    const d = await saveCharacter(source.value, key.value, {
      categories: detail.value.categories, extras: detail.value.extras, custom_tags: detail.value.custom_tags,
    })
    fromDetail(d); msg.success('已保存')
  } catch (e: any) { msg.error('保存失败：' + e.message) }
}
async function reTag() {
  try {
    const d = await tagCharacter(source.value, key.value, genTh.value, charTh.value, localModel.value)
    fromDetail(d); msg.success('反推完成')
  } catch (e: any) { msg.error('反推失败：' + e.message) }
}
async function reClassify() {
  const keep: Record<string, string[]> = {}
  handEdited.value.forEach(k => { keep[k] = detail.value!.categories[k].tags })
  try {
    const d = await reclassifyCharacter(source.value, key.value, keep)
    fromDetail(d); msg.success('重分类完成（跳过手改类）')
  } catch (e: any) { msg.error('重分类失败：' + e.message) }
}
async function uploadImage(file: File) {
  try {
    const r = await uploadCharacterImage(source.value, key.value, file)
    detail.value!.image_override = r.image_override; imgVersion.value++; msg.success('图片已替换')
  } catch (e: any) { msg.error('上传失败：' + e.message) }
}
function onUploadReq({ file }: any) { const f = (file as any)?.file as File | undefined; if (f) uploadImage(f) }
async function toggleFav() {
  try {
    const r = await toggleCharacterFavorite(source.value, key.value)
    detail.value!.favorite = r.favorite
  } catch (e: any) { msg.error('收藏失败：' + e.message) }
}
const refreshing = ref(false)
async function refreshCover() {
  refreshing.value = true
  try {
    await refreshThumb('char', source.value, key.value)
    imgVersion.value++; msg.success('已重新拉取')
  } catch (e: any) { msg.error('拉取失败：' + e.message) }
  finally { refreshing.value = false }
}

const fullPrompt = computed(() => detail.value ? buildPromptWithLocked(detail.value, detail.value.locked_tags) : '')
async function copyPrompt() {
  if (!fullPrompt.value) { msg.warning('暂无提示词'); return }
  try { await navigator.clipboard.writeText(fullPrompt.value); msg.success('已复制完整 prompt') }
  catch { msg.error('复制失败') }
}
const imgSrc = computed(() => detail.value ? detail.value.image_url + (imgVersion.value ? `&_v=${imgVersion.value}` : '') : '')
const hasImage = computed(() => !!imgSrc.value)

defineExpose({ save, reTag, reClassify, uploadImage, toggleFav })
</script>

<template>
  <div v-if="detail" style="display:grid;grid-template-columns:minmax(280px,1fr) minmax(0,2fr);gap:16px">
    <div>
      <n-card>
        <div class="img-wrap">
          <n-image v-if="hasImage" :src="imgSrc" :preview-src="imgSrc" object-fit="contain"
                   style="max-height:420px;width:100%;display:block" />
          <div v-else class="no-img">暂无图片</div>
        </div>
        <div style="font-size:12px;margin-top:8px">
          <div style="margin-bottom:4px">
            <span style="font-weight:600">{{ detail.name }}</span>
            <span v-if="detail.series" style="color:var(--n-text-color-3,#888);margin-left:8px">{{ detail.series }}</span>
          </div>
          <div>{{ detail.source }}</div>
          <div style="margin-top:6px">
            <div style="font-size:13px;margin-bottom:4px">反推模型</div>
            <n-select :value="localModel" :options="taggerOptions" :render-label="renderTaggerLabel"
                      @update:value="(v: string) => localModel = v" size="small" style="max-width:260px" />
            <div v-if="!modelDownloaded" style="margin-top:4px;display:flex;align-items:center;gap:6px">
              <span style="font-size:12px;color:#d03050">{{ tagger.state.taggers.find(t=>t.key===localModel)?.label || localModel }} 未下载</span>
              <n-button size="tiny" :loading="tagger.state.downloading===localModel" @click="doDownload">下载</n-button>
            </div>
          </div>
          <div>通用 <n-input-number v-model:value="genTh" :step="0.05" :min="0" :max="1" size="small" style="width:96px" /><template v-if="localModel !== 'cl_tagger_v2'"> / {{ charLabel }} <n-input-number v-model:value="charTh" :step="0.05" :min="0" :max="1" size="small" style="width:96px" /></template></div>
          <div style="margin-top:6px">
            <div style="color:var(--cat-input-color,#888);margin-bottom:2px">自定义标签</div>
            <n-dynamic-tags :value="detail.custom_tags || []" size="small" @update:value="onCustomTags" />
          </div>
        </div>
        <n-space vertical style="margin-top:8px">
          <n-upload :show-file-list="false" :max="1" accept="image/*" :custom-request="onUploadReq">
            <n-button size="small"><IconPlus/> 替换图片</n-button>
          </n-upload>
          <n-button v-if="source === 'anima'" size="small" :loading="refreshing" @click="refreshCover">重新拉取封面</n-button>
          <n-button size="small" @click="reTag">重新反推</n-button>
          <n-button size="small" @click="reClassify">重分类</n-button>
          <n-button size="small" :type="detail.favorite ? 'warning' : 'default'" @click="toggleFav">
            {{ detail.favorite ? '★ 已收藏' : '☆ 收藏' }}
          </n-button>
        </n-space>
      </n-card>
    </div>
    <div>
      <!-- 🔒 锁定标签区：权威 trigger+core_tags，只读不可编辑 -->
      <div v-if="detail.locked_tags && detail.locked_tags.length" class="locked-box">
        <span class="locked-title">🔒 锁定标签（权威，不可编辑）</span>
        <div class="locked-tags">
          <n-tag v-for="t in detail.locked_tags" :key="'lock-' + t" class="locked-tag" size="small" round :bordered="false" type="warning">{{ '🔒 ' + t }}</n-tag>
        </div>
      </div>
      <n-space align="center" style="margin-bottom:10px">
        <n-radio-group v-model:value="mode" size="small">
          <n-radio-button value="tags">标签</n-radio-button>
          <n-radio-button value="phrase">短句</n-radio-button>
        </n-radio-group>
        <n-button size="small" @click="copyPrompt">复制完整 prompt</n-button>
        <n-button size="small" type="primary" :disabled="!dirty" @click="save">保存</n-button>
      </n-space>
      <TagEditor v-for="[k, title, color] in KEY_TITLES" :key="k" :title="title" :color="color"
                 :mode="mode" :category-key="k"
                 :model-value="detail.categories[k] || { tags: [], phrase: '', user_edited: false }"
                 @update:modelValue="(v) => setCat(k, v)" @apply-phrase="(t) => applyPhrase(k, t)" />
      <TagEditor title="未归类 extras（拖到各类为复制，不会移除原标签）" color="#9E9E9E" :mode="mode"
                 category-key="extras" :model-value="detail.extras"
                 @update:modelValue="setExtras" @apply-phrase="(t) => applyPhrase('extras', t)" />
    </div>
  </div>
</template>

<style scoped>
:deep(.n-image) { display: block; width: 100% }
:deep(.n-image img) { max-width: 100%; max-height: 420px; width: auto; height: auto; object-fit: contain; display: block; margin: 0 auto }
.img-wrap { border-radius: 10px; padding: 8px; display: flex; align-items: center; justify-content: center }
.no-img { height: 200px; display: flex; align-items: center; justify-content: center; font-size: 13px; border-radius: 4px }
.locked-box { border: 1px dashed #d4a017; border-radius: 8px; padding: 8px 10px; margin-bottom: 12px; background: var(--cat-panel-bg, #fafafa) }
.locked-title { font-size: 12px; font-weight: 600; color: #b8860b; display: block; margin-bottom: 6px }
.locked-tags { display: flex; flex-wrap: wrap; gap: 4px }
</style>
