<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NCard, NGrid, NGridItem, NPagination, NEmpty, NSelect, NInput } from 'naive-ui'
import {
  searchCharacters, listCharacterSeries, toggleCharacterFavorite, parseEntryKey,
  type CfListItem,
} from '../api/characterfinder'
import ImageCard from '../components/ImageCard.vue'

const items = ref<CfListItem[]>([])
const total = ref(0)
const page = ref(1)
const size = 50
const query = ref('')
const source = ref('danbooru')
const series = ref<string | null>(null)
const seriesOptions = ref<{ label: string; value: string }[]>([])

const SOURCE_OPTIONS = [
  { label: 'Danbooru', value: 'danbooru' },
  { label: 'e621', value: 'e621' },
  { label: 'Anima', value: 'anima' },
]

// Race-safety：递增的请求序号。慢请求返回时若序号已过期，丢弃其结果，
// 避免旧筛选/旧页码的数据覆盖新页（快速切换 source/翻页场景）。
let lastReq = 0

async function load() {
  const cur = ++lastReq
  const r = await searchCharacters(query.value, source.value, series.value || undefined, page.value, size)
  if (cur !== lastReq) return  // 已被更新的请求取代
  items.value = r.items; total.value = r.total
}
async function loadSeries() {
  const list = await listCharacterSeries(source.value)
  seriesOptions.value = Array.isArray(list) ? list.map(s => ({ label: `${s.series} (${s.count})`, value: s.series })) : []
}
onMounted(() => { load(); loadSeries() })

function onSource(v: string) {
  source.value = v; page.value = 1; series.value = null
  load(); loadSeries()
}
function onSeries(v: string | null) { series.value = v; page.value = 1; load() }

// 防抖 350ms；回车立即
let queryTimer: any = null
function onQuery(v: string) {
  query.value = v
  clearTimeout(queryTimer)
  queryTimer = setTimeout(() => { page.value = 1; load() }, 350)
}
function onQueryEnter() { clearTimeout(queryTimer); page.value = 1; load() }

// cf item → 通用化 ImageCard 的 props 映射
function cardTo(it: CfListItem): string {
  const { source: s, key } = parseEntryKey(it.entry_key)
  return `/characters/${s}/${encodeURIComponent(key)}`
}
function cardImg(it: CfListItem): string {
  return it.thumb_url || ''
}
function cardTags(it: CfListItem): string[] {
  const raw = it.core_tags || it.tag || ''
  return raw.split(',').map(t => t.trim()).filter(Boolean)
}
async function onToggleFav(it: CfListItem) {
  const { source: s, key } = parseEntryKey(it.entry_key)
  try {
    const r = await toggleCharacterFavorite(s, key)
    it.favorite = r.favorite
  } catch { /* 静默：列表态不弹错 */ }
}
</script>

<template>
  <n-card size="small" class="filter-bar" style="margin-bottom:16px">
    <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">
      <div class="field"><span class="field-label">来源</span>
        <n-select :value="source" :options="SOURCE_OPTIONS" size="small" style="width:140px"
                  @update:value="onSource" /></div>
      <div class="field"><span class="field-label">系列</span>
        <n-select :value="series" :options="seriesOptions" clearable filterable size="small"
                  placeholder="全部系列" style="min-width:220px;max-width:320px"
                  @update:value="onSeries" /></div>
      <div class="field"><span class="field-label">搜索</span>
        <n-input :value="query" placeholder="名称 / 触发词" size="small" clearable
                 @update:value="onQuery" @keyup.enter="onQueryEnter"
                 style="min-width:220px;max-width:300px" /></div>
    </div>
  </n-card>
  <n-empty v-if="!items.length" description="没有符合条件的角色" />
  <n-grid v-else cols="2 600:3 900:5 1200:6" :x-gap="12" :y-gap="12">
    <n-grid-item v-for="it in items" :key="it.entry_key">
      <ImageCard :item="it" :to="cardTo(it)" :img-src="cardImg(it)"
                 :title-text="it.name || ''" :tags-list="cardTags(it)"
                 :favorite="it.favorite" @toggle-favorite="onToggleFav(it)" />
    </n-grid-item>
  </n-grid>
  <n-pagination v-if="total > size" v-model:page="page" :item-count="total"
                :page-size="size" @update:page="load" style="margin-top:16px" />
</template>

<style scoped>
.field { display: flex; align-items: center; gap: 8px }
.field-label { font-size: 13px; font-weight: 600; color: var(--n-text-color-3, #6b7280); min-width: 28px }
</style>
