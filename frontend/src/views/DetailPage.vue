<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NSpace, NButton, NRadioGroup, NRadioButton, NImage, NCard, NInputNumber, NInput, NDynamicTags, useMessage, NPopconfirm } from 'naive-ui'
import TagEditor from '../components/TagEditor.vue'
import { getMeta, saveMeta, tagImage, reclassify, deleteImage, fileUrl, applyCategoryRules } from '../api/client'
import { buildPrompt } from '../detail-utils'

const route = useRoute(); const router = useRouter(); const msg = useMessage()
const id = computed(() => route.params.id as string)
const meta = ref<any>(null)
const mode = ref<'tags' | 'phrase'>('tags')
const dirty = ref(false)
const genTh = ref(0.35)
const charTh = ref(0.9)

async function load() {
  const cur = id.value
  const m = await getMeta(cur)
  if (cur !== id.value) return  // 已切到其它图，丢弃旧结果防竞态
  meta.value = m; dirty.value = false
  genTh.value = m.tagger.gen_threshold
  charTh.value = m.tagger.char_threshold
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
  meta.value = await tagImage(id.value, genTh.value, charTh.value)
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
        <n-image :src="fileUrl(id, meta.image.thumb)" :preview-src="fileUrl(id, meta.image.original)" object-fit="contain" style="max-height:420px;width:100%;display:block" />
        <div style="font-size:12px;margin-top:8px">
          <div style="margin-bottom:4px">
            名称 <n-input :value="meta.source_name" size="small" @update:value="onName" placeholder="图片名称" style="width:240px" />
          </div>
          <div>{{ meta.image.width }}×{{ meta.image.height }} · {{ meta.model }}</div>
          <div>通用 <n-input-number v-model:value="genTh" :step="0.05" :min="0" :max="1" size="small" style="width:96px" /> / 角色 <n-input-number v-model:value="charTh" :step="0.05" :min="0" :max="1" size="small" style="width:96px" /></div>
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
</style>
