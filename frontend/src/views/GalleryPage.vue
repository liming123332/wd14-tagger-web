<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NGrid, NGridItem, NPagination, NEmpty, NDatePicker, NSelect, NInput } from 'naive-ui'
import { listImages, listTags } from '../api/client'
import ImageCard from '../components/ImageCard.vue'

const items = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const size = 24
const dateTs = ref<number | null>(null)
const selTags = ref<string[]>([])
const tagOptions = ref<{ label: string; value: string }[]>([])
const promptText = ref('')

function dateStr(): string | undefined {
  if (!dateTs.value) return undefined
  const d = new Date(dateTs.value)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}${m}${day}`
}

async function load() {
  const r = await listImages(page.value, size, dateStr(), selTags.value, promptText.value)
  items.value = r.items; total.value = r.total
}
// 拉取全库标签计数，下拉显示「tag (n)」并按热度排序
async function loadTags() {
  const counts = await listTags()
  tagOptions.value = Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .map(([k, n]) => ({ label: `${k} (${n})`, value: k }))
}
onMounted(() => { load(); loadTags() })

function onDate(v: number | null) {
  dateTs.value = v
  page.value = 1
  load()
}
function onTags(v: string[]) {
  selTags.value = v
  page.value = 1
  load()
}
// 提示词输入：防抖 350ms 触发交集筛选；回车立即触发
let promptTimer: any = null
function onPrompt(v: string) {
  promptText.value = v
  clearTimeout(promptTimer)
  promptTimer = setTimeout(() => { page.value = 1; load() }, 350)
}
function onPromptEnter() {
  clearTimeout(promptTimer)
  page.value = 1
  load()
}
const hasFilter = () => !!(dateTs.value || selTags.value.length || promptText.value.trim())
</script>

<template>
  <div style="margin-bottom:12px;display:flex;align-items:center;gap:12px;flex-wrap:wrap">
    <span style="font-size:13px">按日期</span>
    <n-date-picker v-model:value="dateTs" type="date" clearable size="small"
                   @update:value="onDate" style="width:160px" />
    <span style="font-size:13px">按标签</span>
    <n-select v-model:value="selTags" multiple clearable filterable size="small"
              :options="tagOptions" placeholder="多选标签（交集筛选）"
              @update:value="onTags" style="min-width:240px;max-width:360px" />
    <span style="font-size:13px">按提示词</span>
    <n-input :value="promptText" placeholder="提示词（逗号或空格分隔，交集）" size="small" clearable
             @update:value="onPrompt" @keyup.enter="onPromptEnter"
             style="min-width:240px;max-width:320px" />
  </div>
  <n-empty v-if="!items.length" :description="hasFilter() ? '没有符合条件的图片' : '还没有图片，先去上传'" />
  <n-grid v-else cols="2 600:3 900:5 1200:6" :x-gap="12" :y-gap="12">
    <n-grid-item v-for="it in items" :key="it.id">
      <ImageCard :item="it" />
    </n-grid-item>
  </n-grid>
  <n-pagination v-if="total > size" v-model:page="page" :item-count="total"
                :page-size="size" @update:page="load" style="margin-top:16px" />
</template>
