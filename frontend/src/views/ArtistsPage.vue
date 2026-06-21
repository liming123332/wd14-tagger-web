<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { NCard, NSelect, NInput, NEmpty, NPagination, NGrid, NGridItem, useMessage } from 'naive-ui'
import ImageCard from '../components/ImageCard.vue'
import { searchArtists, toggleArtistFavorite, listCfRecent, parseEntryKey } from '../api/characterfinder'

const msg = useMessage()
const SOURCE_OPTIONS = [
  { label: 'Anima 画师', value: 'anima' },
  { label: 'Danbooru 画师', value: 'danbooru' },
]
const source = ref('anima')
const query = ref('')
const page = ref(1); const size = ref(50)
const total = ref(0); const items = ref<any[]>([])
const recentItems = ref<any[]>([])
const loading = ref(false)

let timer: any = null
let lastReq = 0
async function load() {
  loading.value = true
  const myReq = ++lastReq
  try {
    const r = await searchArtists(query.value, source.value, page.value, size.value)
    if (myReq !== lastReq) return
    items.value = r.items; total.value = r.total
  } catch (e: any) { msg.error('加载失败：' + e.message) } finally { if (myReq === lastReq) loading.value = false }
}
onMounted(() => {
  load()
  listCfRecent('artist', 10).then(r => { recentItems.value = r.items || [] }).catch(() => {})
})
function onQuery() { clearTimeout(timer); timer = setTimeout(() => { page.value = 1; load() }, 350) }
function onSource() { page.value = 1; load() }
function onPage(p: number) { page.value = p; load() }
onBeforeUnmount(() => clearTimeout(timer))

function cardTo(item: any) {
  const { source: src, key } = parseEntryKey(item.entry_key)
  return `/artists/${src}/${encodeURIComponent(key)}`
}
function cardImg(item: any) { return item.thumb1_url }
function cardTags(item: any) { return item.tag ? String(item.tag).split(',').map((s: string) => s.trim()).filter(Boolean) : [] }
async function onToggleFav(item: any) {
  const { source: src, key } = parseEntryKey(item.entry_key)
  try {
    const r = await toggleArtistFavorite(src, key)
    const t = items.value.find(i => i.entry_key === item.entry_key)
    if (t) t.favorite = r.favorite
  } catch (e: any) { msg.error('收藏失败：' + e.message) }
}
</script>

<template>
  <div v-if="recentItems.length" class="recent-bar">
    <span class="recent-label">最近查看</span>
    <div class="recent-scroll">
      <ImageCard v-for="it in recentItems" :key="it.entry_key" :item="it" :to="cardTo(it)"
                 :img-src="cardImg(it)" :title-text="it.name || ''"
                 :tags-list="cardTags(it)" :favorite="!!it.favorite" style="width:140px" />
    </div>
  </div>
  <n-card class="filter-bar">
    <n-select v-model:value="source" :options="SOURCE_OPTIONS" size="small" style="width:160px" @update:value="onSource" />
    <n-input v-model:value="query" placeholder="搜索画师名 / tag" size="small" clearable style="width:240px" @update:value="onQuery" />
  </n-card>
  <n-empty v-if="!loading && items.length === 0" description="暂无画师" style="margin:40px 0" />
  <n-grid cols="2 600:3 900:5 1200:6" :x-gap="12" :y-gap="12">
    <n-grid-item v-for="item in items" :key="item.entry_key">
      <ImageCard :item="item" :to="cardTo(item)" :img-src="cardImg(item)" :title-text="item.name"
                 :tags-list="cardTags(item)" :favorite="!!item.favorite" @toggle-favorite="onToggleFav(item)" />
    </n-grid-item>
  </n-grid>
  <n-pagination v-if="total > size" :page="page" :item-count="total" :page-size="size"
                :page-slot="7" style="margin-top:16px;justify-content:center" @update:page="onPage" />
</template>

<style scoped>
.filter-bar { margin-bottom: 12px }
.filter-bar :deep(.n-card__content) { display: flex; gap: 8px; align-items: center; flex-wrap: wrap }
.recent-bar { margin-bottom: 12px }
.recent-label { font-size: 12px; font-weight: 600; color: var(--n-text-color-3, #6b7280) }
.recent-scroll { display: flex; gap: 8px; overflow-x: auto; padding: 6px 0 4px }
.recent-scroll :deep(.card) { flex: 0 0 140px }
</style>
