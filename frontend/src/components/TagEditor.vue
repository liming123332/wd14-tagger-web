<script setup lang="ts">
import { ref, watch } from 'vue'
import { NTag, NInput, NButton, NSpace, NPopconfirm } from 'naive-ui'
import { parsePhrase } from '../detail-utils'

const props = defineProps<{
  title: string; color: string
  modelValue: { tags: string[]; phrase: string; user_edited: boolean }
  mode: 'tags' | 'phrase'
}>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: any): void
  (e: 'applyPhrase', tags: string[]): void
}>()

const newTag = ref('')
const dragging = ref(false)

watch(() => props.modelValue, () => {}, { deep: true })

function patch(p: Partial<typeof props.modelValue>) {
  emit('update:modelValue', { ...props.modelValue, ...p })
}
function addTag() {
  const t = newTag.value.trim(); if (!t) return
  if (!props.modelValue.tags.includes(t)) patch({ tags: [...props.modelValue.tags, t], user_edited: true })
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
</script>

<template>
  <div class="cat-panel" :style="{ borderColor: color }" @dragover.prevent="dragging = true"
       @dragleave.prevent="dragging = false" @drop.prevent="onDrop">
    <div class="cat-title" :style="{ background: color }">{{ title }}</div>
    <div class="cat-body">
      <template v-if="mode === 'tags'">
        <n-space size="small">
          <n-tag v-for="(t, i) in modelValue.tags" :key="t + i" closable @dragstart="($event as any).dataTransfer.setData('text/tag', t)"
                 @close="removeTag(i)">{{ t }}</n-tag>
        </n-space>
        <n-space style="margin-top:6px">
          <n-input v-model:value="newTag" size="small" placeholder="添加标签" @keyup.enter="addTag" style="width:160px" />
          <n-button size="small" @click="addTag">+</n-button>
        </n-space>
      </template>
      <template v-else>
        <textarea class="phrase-box" :value="modelValue.phrase" @input="onPhraseInput"
                  rows="2" placeholder="短句（用逗号分隔多标签）"></textarea>
        <n-popconfirm @positive-click="applyPhrase">
          <template #trigger><n-button size="tiny" :disabled="!modelValue.user_edited">应用短句到标签</n-button></template>
          将用短句覆盖当前标签？
        </n-popconfirm>
      </template>
      <div v-if="dragging" class="drop-hint">拖到此处（复制）</div>
    </div>
  </div>
</template>

<style scoped>
.cat-panel { border-left: 4px solid #888; border-radius: 6px; overflow: hidden; margin-bottom: 10px; background: #fafafa; }
.cat-title { color: #fff; font-weight: 600; padding: 4px 10px; }
.cat-body { padding: 8px 10px; position: relative; }
.phrase-box { width: 100%; resize: vertical; font-family: inherit; }
.drop-hint { position: absolute; inset: 0; background: rgba(0,128,0,.12); display:flex;align-items:center;justify-content:center; }
</style>
