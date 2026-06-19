<script setup lang="ts">
import { ref, computed, watch, onMounted, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NSpace, NButton, NRadioGroup, NRadioButton, NImage, NCard, NInputNumber, NInput, NDynamicTags, useMessage, NPopconfirm, NSelect, NTag } from 'naive-ui'
import TagEditor from '../components/TagEditor.vue'
import { getMeta, saveMeta, tagImage, reclassify, deleteImage, fileUrl, applyCategoryRules } from '../api/client'
import { useTagger } from '../composables/useTagger'
import { buildPrompt } from '../detail-utils'

const tagger = useTagger()

const route = useRoute(); const router = useRouter(); const msg = useMessage()
const id = computed(() => route.params.id as string)
const meta = ref<any>(null)
const mode = ref<'tags' | 'phrase'>('tags')
const dirty = ref(false)
const genTh = ref(0.35)
const charTh = ref(0.9)
// 详情页独立模型选择：默认=该图当前 meta.model，切换不影响上传页全局选中。
const localModel = ref('')
const taggerOptions = computed(() => tagger.state.taggers.map(t => ({
  label: t.label, value: t.key, downloaded: t.downloaded,
})))
// naive-ui NSelect 的 render-label 是 prop（render function），非插槽：同时渲染面板项与 trigger。
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
// charLabel 跟随当前选中模型（localModel）：选 cl_tagger 时提示「仅 cl_tagger 生效」。
const charLabel = computed(() => localModel.value === 'cl_tagger' ? '角色名称识别阈值（仅 cl_tagger 生效）' : '角色')
// 用户主动切换模型时按 cl 适配角色阈值（cl→0.6，wd 系→0.9）；
// load 载入该图 meta 时用 flag 跳过，保留原图记录的阈值不被覆盖。
let modelChangeFromLoad = false
watch(localModel, (m) => {
  if (modelChangeFromLoad) { modelChangeFromLoad = false; return }
  charTh.value = m === 'cl_tagger' ? 0.6 : 0.9
})

async function load() {
  const cur = id.value
  const m = await getMeta(cur)
  if (cur !== id.value) return  // 已切到其它图，丢弃旧结果防竞态
  meta.value = m; dirty.value = false
  genTh.value = m.tagger.gen_threshold
  charTh.value = m.tagger.char_threshold
  modelChangeFromLoad = true
  localModel.value = m.model
}
watch(id, load, { immediate: true })

const KEY_TITLES: [string, string, string][] = [
  ['head', '角色头部', '#4CAF50'], ['clothing', '服装', '#2196F3'],
  ['view', '视角构图', '#9C27B0'], ['action', '动作', '#FF9800'],
  ['scene', '场景', '#795548'], ['quality', '质量词（预设）', '#607D8B'],
]

function setCat(key: string, val: any) {
  meta.value.categories[key] = val; dirty.value = true
}
function setExtras(val: any) { meta.value.extras = val; dirty.value = true }

// 改名 / 自定义标签：改即置脏，复用下方 save() 走 PUT 整个 meta。
function onName(v: string) { meta.value.source_name = v; dirty.value = true }
function onTags(v: string[]) { meta.value.tags = v; dirty.value = true }

// 把该分类当前 tags 存入分类词表（tag_rules.yaml exact）并 reload，下次反推生效
async function onApplyRule(key: string, title: string, tags: string[]) {
  if (!tags || !tags.length) { msg.warning('该分类暂无标签可应用'); return }
  try { await applyCategoryRules(key, tags); msg.success(`已加入「${title}」分类词表，下次反推自动归类`) }
  catch (e: any) { msg.error('应用失败：' + e.message) }
}

// 应用短句：从 phrase 拆 tags 覆盖该类
function applyPhrase(key: string, tags: string[]) {
  const cur = key === 'extras' ? meta.value.extras : meta.value.categories[key]
  const next = { ...cur, tags, user_edited: true }
  if (key === 'extras') setExtras(next); else setCat(key, next)
}

async function save() {
  try { await saveMeta(id.value, meta.value); dirty.value = false; msg.success('已保存') }
  catch (e: any) { msg.error('保存失败：' + e.message) }
}

async function reTag() {
  meta.value = await tagImage(id.value, genTh.value, charTh.value, localModel.value)
  msg.success('反推完成')
}
async function reClassify() {
  meta.value = await reclassify(id.value); msg.success('重分类完成（跳过手改类）')
}
async function del() {
  await deleteImage(id.value); msg.success('已删除'); router.push('/gallery')
}

const fullPrompt = computed(() => meta.value ? buildPrompt(meta.value) : '')
async function copyPrompt() {
  try { await navigator.clipboard.writeText(fullPrompt.value); msg.success('已复制完整 prompt') }
  catch (e: any) { msg.error('复制失败：' + e.message) }
}
</script>

<template>
  <div v-if="meta" style="display:grid;grid-template-columns:minmax(280px,1fr) minmax(0,2fr);gap:16px">
    <div>
      <n-card>
        <div class="img-wrap">
          <n-image :src="fileUrl(id, meta.image.thumb)" :preview-src="fileUrl(id, meta.image.original)" object-fit="contain" style="max-height:420px;width:100%;display:block" />
        </div>
        <div style="font-size:12px;margin-top:8px">
          <div style="margin-bottom:4px">
            名称 <n-input :value="meta.source_name" size="small" @update:value="onName" placeholder="图片名称" style="width:240px" />
          </div>
          <div>{{ meta.image.width }}×{{ meta.image.height }} · {{ meta.model }}</div>
          <div style="margin-top:6px">
            <div style="font-size:13px;margin-bottom:4px">反推模型</div>
            <n-select
              :value="localModel"
              :options="taggerOptions"
              :render-label="renderTaggerLabel"
              @update:value="(v: string) => localModel = v"
              size="small"
              style="max-width:260px"
            />
            <div v-if="!modelDownloaded" style="margin-top:4px;display:flex;align-items:center;gap:6px">
              <span style="font-size:12px;color:#d03050">{{ tagger.state.taggers.find(t=>t.key===localModel)?.label || localModel }} 未下载</span>
              <n-button size="tiny" :loading="tagger.state.downloading===localModel" @click="doDownload">下载</n-button>
            </div>
          </div>
          <div>通用 <n-input-number v-model:value="genTh" :step="0.05" :min="0" :max="1" size="small" style="width:96px" /> / {{ charLabel }} <n-input-number v-model:value="charTh" :step="0.05" :min="0" :max="1" size="small" style="width:96px" /></div>
          <div style="margin-top:6px">
            <div style="color:#888;margin-bottom:2px">自定义标签（用于图库筛选）</div>
            <n-dynamic-tags :value="meta.tags || []" size="small" @update:value="onTags" />
          </div>
        </div>
        <n-space vertical style="margin-top:8px">
          <n-button size="small" @click="reTag">重新反推</n-button>
          <n-button size="small" @click="reClassify">重分类</n-button>
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
        <n-button size="small" @click="copyPrompt">复制完整 prompt</n-button>
        <n-button size="small" type="primary" :disabled="!dirty" @click="save">保存</n-button>
      </n-space>
      <TagEditor v-for="[key, title, color] in KEY_TITLES" :key="key" :title="title" :color="color"
                 :mode="mode" :category-key="key"
                 :model-value="meta.categories[key] || { tags: [], phrase: '', user_edited: false }"
                 @update:modelValue="(v) => setCat(key, v)" @apply-phrase="(t) => applyPhrase(key, t)"
                 @apply-rule="(t) => onApplyRule(key, title, t)" />
      <TagEditor title="未归类 extras（拖到各类为复制，不会移除原标签）" color="#9E9E9E" :mode="mode"
                 category-key="extras"
                 :model-value="meta.extras"
                 @update:modelValue="setExtras" @apply-phrase="(t) => applyPhrase('extras', t)" />
    </div>
  </div>
</template>

<style scoped>
/* n-image 默认 inline-flex（shrink-to-fit），img 的 width:100% 因父级宽度
   依赖内容而失效，退回原图自然宽度（如 4884px）溢出容器；视口变化
   （开 DevTools / 调整窗口）时图片位置随之偏移。
   强制 n-image 为 block + 100% 宽，img 才能按容器宽度正确缩放。 */
:deep(.n-image) {
  display: block;
  width: 100%;
}
:deep(.n-image img) {
  max-width: 100%;
  height: auto;
}
.img-wrap {
  background: #0f1115;
  border-radius: 10px;
  padding: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
