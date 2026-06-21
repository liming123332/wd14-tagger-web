<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { NCard, NTabs, NTab, NInput, NGrid, NGridItem, NEmpty, useMessage } from 'naive-ui'
import {
  listCfFavorites, toggleCharacterFavorite, toggleArtistFavorite, parseEntryKey,
  type CfListItem,
} from '../api/characterfinder'
import ImageCard from '../components/ImageCard.vue'

const msg = useMessage()
const kind = ref<'char' | 'artist'>('char')
const items = ref<CfListItem[]>([])
const keyword = ref('')
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    items.value = (await listCfFavorites(kind.value)).items
  } catch (e: any) { msg.error('加载失败：' + e.message) } finally { loading.value = false }
}
onMounted(load)

function onKind(v: 'char' | 'artist') { kind.value = v; load() }

// 前端子串过滤（收藏量级小，无需后端分页）
const filtered = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  if (!k) return items.value
  return items.value.filter(it =>
    (it.name || '').toLowerCase().includes(k) ||
    (it.core_tags || it.tag || '').toLowerCase().includes(k),
  )
})

function cardTo(it: CfListItem): string {
  const { source: s, key } = parseEntryKey(it.entry_key)
  return kind.value === 'artist' ? `/artists/${s}/${encodeURIComponent(key)}` : `/characters/${s}/${encodeURIComponent(key)}`
}
function cardImg(it: CfListItem): string {
  return kind.value === 'artist' ? (it.thumb1_url || '') : (it.thumb_url || '')
}
function cardTags(it: CfListItem): string[] {
  const raw = kind.value === 'artist' ? (it.tag || '') : (it.core_tags || '')
  return raw.split(',').map(t => t.trim()).filter(Boolean)
}

// 乐观移除：点掉收藏后从列表移除（不再属于收藏列表）
async function onToggleFav(it: CfListItem) {
  const { source: s, key } = parseEntryKey(it.entry_key)
  try {
    const r = kind.value === 'artist'
      ? await toggleArtistFavorite(s, key)
      : await toggleCharacterFavorite(s, key)
    if (!r.favorite) items.value = items.value.filter(i => i.entry_key !== it.entry_key)
  } catch (e: any) { msg.error('操作失败：' + e.message) }
}
</script>

<template>
  <n-card size="small" class="filter-bar" style="margin-bottom:16px">
    <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">
      <n-tabs type="line" :value="kind" size="small" @update:value="onKind">
        <n-tab name="char">角色收藏</n-tab>
        <n-tab name="artist">艺术家收藏</n-tab>
      </n-tabs>
      <n-input :value="keyword" placeholder="搜索名称 / tag" size="small" clearable
               @update:value="(v: string) => keyword = v"
               style="min-width:220px;max-width:300px" />
    </div>
  </n-card>
  <n-empty v-if="!filtered.length" :description="keyword ? '没有符合条件的收藏' : '还没有收藏，去角色/艺术家列表收藏吧'" />
  <n-grid v-else cols="2 600:3 900:5 1200:6" :x-gap="12" :y-gap="12">
    <n-grid-item v-for="it in filtered" :key="it.entry_key">
      <ImageCard :item="it" :to="cardTo(it)" :img-src="cardImg(it)"
                 :title-text="it.name || ''" :tags-list="cardTags(it)"
                 :favorite="it.favorite" @toggle-favorite="onToggleFav(it)" />
    </n-grid-item>
  </n-grid>
</template>

<style scoped>
.field { display: flex; align-items: center; gap: 8px }
.field-label { font-size: 13px; font-weight: 600; color: var(--n-text-color-3, #6b7280); min-width: 28px }
</style>
