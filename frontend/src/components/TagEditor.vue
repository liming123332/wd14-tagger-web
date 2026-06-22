<script setup lang="ts">
import { ref, watch } from 'vue'
import { NTag, NInput, NButton, NSpace, NPopconfirm, useMessage } from 'naive-ui'
import { parsePhrase } from '../detail-utils'
import { useTranslator } from '../composables/useTranslator'
import { translateToTags } from '../api/client'

const props = defineProps<{
  title: string; color: string
  modelValue: { tags: string[]; phrase: string; user_edited: boolean }
  mode: 'tags' | 'phrase'
  categoryKey?: string
  lockedTags?: string[]
}>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: any): void
  (e: 'applyPhrase', tags: string[]): void
  (e: 'applyRule', tags: string[]): void
}>()

const msg = useMessage()
const translator = useTranslator()
const newTag = ref('')
const dragging = ref(false)

watch(() => props.modelValue, () => {}, { deep: true })

function patch(p: Partial<typeof props.modelValue>) {
  emit('update:modelValue', { ...props.modelValue, ...p })
}
const adding = ref(false)
async function addTag() {
  const raw = newTag.value.trim(); if (!raw) return
  // 含中文 → 按 [，,] 拆成多个中文词，翻译成英文标签再加入；纯英文/标签直接加（自动识别）
  if (/[一-鿿]/.test(raw)) {
    const zhWords = raw.split(/[，,]/).map(s => s.trim()).filter(Boolean)
    newTag.value = ''
    if (!zhWords.length) return
    adding.value = true
    try {
      const { results } = await translateToTags(zhWords)
      const tags = results.filter(t => t && !props.modelValue.tags.includes(t))
      if (tags.length) {
        patch({ tags: [...props.modelValue.tags, ...tags], user_edited: true })
        msg.success(`已翻译添加 ${tags.length} 个标签`)
      } else {
        msg.info('无新标签可添加')
      }
    } catch (e: any) {
      msg.error('中文翻译失败：' + (e?.message || '请先下载翻译模型'))
    } finally {
      adding.value = false
    }
    return
  }
  if (!props.modelValue.tags.includes(raw)) patch({ tags: [...props.modelValue.tags, raw], user_edited: true })
  newTag.value = ''
}
function removeTag(i: number) {
  const tags = [...props.modelValue.tags]; tags.splice(i, 1)
  patch({ tags, user_edited: true })
}
function onPhraseInput(e: any) { patch({ phrase: e.target.value, user_edited: true }) }
function applyPhrase() { emit('applyPhrase', parsePhrase(props.modelValue.phrase)) }

function onDrop(e: DragEvent) {
  dragging.value = false
  const tag = e.dataTransfer?.getData('text/tag'); if (!tag) return
  if (!props.modelValue.tags.includes(tag)) patch({ tags: [...props.modelValue.tags, tag], user_edited: true })
}

// 复制该分类当前提示词：tags 模式取标签逗号拼接，phrase 模式取短句文本
async function copyCurrent() {
  const text = props.mode === 'tags'
    ? (props.modelValue.tags || []).join(', ')
    : (props.modelValue.phrase || '')
  try { await navigator.clipboard.writeText(text); msg.success('已复制当前提示词') }
  catch { msg.error('复制失败') }
}

// 翻译本分类：收集 tags（含 lockedTags 权威标签），未下载则自动下，结果进 translator.translations 缓存。
// 翻译不落地（刷新页面即消失）；n-tag 据 translations[t] 原位显示中文小字。
async function translateCat() {
  const tags = [...(props.lockedTags || []), ...(props.modelValue.tags || [])]
  if (!tags.length) { msg.warning('该分类暂无标签可翻译'); return }
  try {
    await translator.translate(tags)
    msg.success('已翻译')
  } catch (e: any) { msg.error('翻译失败：' + e.message) }
}
</script>

<template>
  <div class="cat-panel" :style="{ borderColor: color }" @dragover.prevent="dragging = true"
       @dragleave.prevent="dragging = false" @drop.prevent="onDrop">
    <div class="cat-title" :style="{ background: color }">{{ title }}</div>
    <div class="cat-body">
      <!-- 🔒 锁定标签：来自权威数据（角色 trigger+core_tags / 画师 tag），只读不可增删/拖拽 -->
      <div v-if="lockedTags && lockedTags.length && mode === 'tags'" class="locked-tags">
        <n-tag v-for="t in lockedTags" :key="'lock-' + t" class="locked-tag" size="small" round :bordered="false" type="warning">
          <span class="tag-inner"><span>🔒 {{ t.replaceAll('_', ' ') }}</span><span v-if="translator.translations[t]" class="tag-zh">{{ translator.translations[t] }}</span></span>
        </n-tag>
      </div>
      <template v-if="mode === 'tags'">
        <n-space size="small">
          <n-tag v-for="(t, i) in modelValue.tags" :key="t + i" closable @dragstart="($event as any).dataTransfer.setData('text/tag', t)"
                 @close="removeTag(i)">
            <span class="tag-inner"><span>{{ t.replaceAll('_', ' ') }}</span><span v-if="translator.translations[t]" class="tag-zh">{{ translator.translations[t] }}</span></span>
          </n-tag>
        </n-space>
        <n-space style="margin-top:6px">
          <n-input v-model:value="newTag" size="small" placeholder="添加标签（中文自动转标签）" :loading="adding" @keyup.enter="addTag" style="width:160px" />
          <n-button size="small" :loading="adding" @click="addTag">+</n-button>
          <n-button v-if="categoryKey && categoryKey !== 'extras'" size="tiny" type="info" ghost
                    @click="$emit('applyRule', modelValue.tags)">应用到分类词表</n-button>
          <n-button size="tiny" :loading="translator.state.translating" @click="translateCat">翻译本分类</n-button>
          <n-button size="tiny" @click="copyCurrent">复制当前提示词</n-button>
        </n-space>
      </template>
      <template v-else>
        <textarea class="phrase-box" :value="modelValue.phrase" @input="onPhraseInput"
                  rows="2" placeholder="短句（用逗号分隔多标签）"></textarea>
        <n-space style="margin-top:6px">
          <n-popconfirm @positive-click="applyPhrase">
            <template #trigger><n-button size="tiny" :disabled="!modelValue.user_edited">应用短句到标签</n-button></template>
            将用短句覆盖当前标签？
          </n-popconfirm>
          <n-button size="tiny" @click="copyCurrent">复制当前提示词</n-button>
        </n-space>
      </template>
      <div v-if="dragging" class="drop-hint">拖到此处（复制）</div>
    </div>
  </div>
</template>

<style scoped>
.cat-panel { border-left: 4px solid #888; border-radius: 6px; overflow: hidden; margin-bottom: 10px; background: var(--cat-panel-bg, #fafafa); }
.cat-title { color: #fff; font-weight: 600; padding: 4px 10px; }
.cat-body { padding: 8px 10px; position: relative; }
.phrase-box { width: 100%; resize: vertical; font-family: inherit; background: var(--cat-input-bg, #fff); color: var(--cat-input-color, inherit); }
.drop-hint { position: absolute; inset: 0; background: rgba(0,128,0,.12); display:flex;align-items:center;justify-content:center; }
.locked-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px }
/* n-tag 内部两行：英文标签 + 中文释义小字（翻译后原位显示，来自 translator.translations 缓存） */
.tag-inner { display: flex; flex-direction: column; line-height: 1.2 }
.tag-zh { font-size: 11px; color: var(--n-text-color-3, #999); margin-top: 1px }
/* n-tag 默认单行高度、上下无 padding；塞两行中文小字后底部被胶囊裁，需增高 + 留上下 padding */
.cat-body :deep(.n-tag) { height: auto }
.cat-body :deep(.n-tag__content) { padding-top: 4px; padding-bottom: 4px }
</style>
