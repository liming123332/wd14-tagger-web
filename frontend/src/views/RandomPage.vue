<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NGrid, NGridItem, NEmpty, NButton, NSelect } from 'naive-ui'
import { randomImages } from '../api/client'
import {
  randomCf, toggleCharacterFavorite, toggleArtistFavorite, parseEntryKey,
  type CfListItem,
} from '../api/characterfinder'
import { IconRandom } from '../components/icons'
import ImageCard from '../components/ImageCard.vue'

const items = ref<any[]>([])
const size = 24
const loading = ref(false)

const source = ref<'gallery' | 'characters' | 'artists'>('gallery')
const cfSource = ref<'danbooru' | 'anima'>('anima')

const SOURCE_OPTIONS = [
  { label: '图库', value: 'gallery' },
  { label: '角色图鉴', value: 'characters' },
  { label: '艺术家', value: 'artists' },
]
const CF_SOURCE_OPTIONS = [
  { label: 'Anima', value: 'anima' },
  { label: 'Danbooru', value: 'danbooru' },
]

async function shuffle() {
  loading.value = true
  try {
    if (source.value === 'gallery') {
      items.value = (await randomImages(size)).items
    } else {
      const type = source.value === 'characters' ? 'characters' : 'artists'
      items.value = (await randomCf(type, cfSource.value, size)).items
    }
  } finally {
    loading.value = false
  }
}
onMounted(shuffle)

function onSource(v: 'gallery' | 'characters' | 'artists') {
  source.value = v
  // 立即清空旧 items：避免「source 已变、items 尚未异步替换」的中间帧拿旧数据
  // （图库 item 无 entry_key）走 v-else 渲染 cardTo→parseEntryKey(undefined) 崩溃
  items.value = []
  shuffle()
}
function onCfSource(v: 'danbooru' | 'anima') {
  cfSource.value = v
  items.value = []
  shuffle()
}

// cf 卡片映射（gallery 用 ImageCard 默认 props，不走这些函数）
function cardTo(it: CfListItem): string {
  // 防御：item 若是上一来源残留（图库 item 无 entry_key），不跳转，避免 parseEntryKey(undefined) 崩
  if (!it.entry_key) return ''
  const { source: s, key } = parseEntryKey(it.entry_key)
  return source.value === 'artists' ? `/artists/${s}/${encodeURIComponent(key)}` : `/characters/${s}/${encodeURIComponent(key)}`
}
function cardImg(it: CfListItem): string {
  return source.value === 'artists' ? (it.thumb1_url || '') : (it.thumb_url || '')
}
function cardTags(it: CfListItem): string[] {
  const raw = source.value === 'artists' ? (it.tag || '') : (it.core_tags || '')
  return raw.split(',').map(t => t.trim()).filter(Boolean)
}
async function onToggleFav(it: CfListItem) {
  const { source: s, key } = parseEntryKey(it.entry_key)
  try {
    const r = source.value === 'artists'
      ? await toggleArtistFavorite(s, key)
      : await toggleCharacterFavorite(s, key)
    it.favorite = r.favorite
  } catch { /* 静默：随机页不弹错 */ }
}
</script>

<template>
  <div class="bar">
    <div class="field">
      <span class="field-label">来源</span>
      <n-select :value="source" :options="SOURCE_OPTIONS" size="small" style="width:140px" @update:value="onSource" />
      <n-select v-if="source !== 'gallery'" :value="cfSource" :options="CF_SOURCE_OPTIONS" size="small"
                style="width:130px" @update:value="onCfSource" />
    </div>
    <n-button type="primary" size="small" :loading="loading" @click="shuffle"><IconRandom/> 再抽一页</n-button>
  </div>
  <n-empty v-if="!items.length" :description="source === 'gallery' ? '图库还没有图片，先去上传' : '暂无随机项'" />
  <n-grid v-else cols="2 600:3 900:5 1200:6" :x-gap="12" :y-gap="12">
    <n-grid-item v-for="it in items" :key="(it.entry_key as string) ?? (it.id as string)">
      <ImageCard v-if="source === 'gallery'" :item="it" />
      <ImageCard v-else :item="it" :to="cardTo(it)" :img-src="cardImg(it)"
                 :title-text="it.name || ''" :tags-list="cardTags(it)"
                 :favorite="it.favorite" @toggle-favorite="onToggleFav(it)" />
    </n-grid-item>
  </n-grid>
</template>

<style scoped>
.bar { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; flex-wrap: wrap }
.field { display: flex; align-items: center; gap: 8px }
.field-label { font-size: 13px; font-weight: 600; color: var(--n-text-color-3, #6b7280); min-width: 28px }
</style>
