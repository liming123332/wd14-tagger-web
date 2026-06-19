<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  NGrid, NGridItem, NInput, NButton, NCard, NImage, NTag, NEmpty, NSpace, NPopconfirm, useMessage,
} from 'naive-ui'
import { useRouter } from 'vue-router'
import { listPromptbox, deletePromptbox, promptboxImageUrl, type PromptboxItem } from '../api/client'

// 「收藏列表」独立页签：搜索 + 卡片网格（复用图库 n-grid/卡片视觉）+ 跳转按钮。
// 与 PromptBoxPage（拆分工作台）分工：这里只读+管理已保存收藏，新建/反推去工作台。

const router = useRouter()
const msg = useMessage()
const items = ref<PromptboxItem[]>([])
const keyword = ref('')

const ORDER = ['quality', 'head', 'clothing', 'view', 'action', 'scene'] as const
const TITLES: Record<string, string> = {
  quality: '质量', head: '头部', clothing: '服装', view: '视角', action: '动作', scene: '场景',
}

async function load() {
  try { items.value = await listPromptbox() } catch (e: any) { msg.error('加载失败：' + e.message) }
}
onMounted(load)

// 前端子串过滤（收藏量级小，无需后端分页/防抖）：标题或 raw_prompt 命中即保留
const filtered = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  if (!k) return items.value
  return items.value.filter(it =>
    (it.title || '').toLowerCase().includes(k) ||
    (it.raw_prompt || '').toLowerCase().includes(k),
  )
})

function catCount(it: PromptboxItem, key: string): number {
  return (it.categories[key] || []).length
}

async function doDelete(id: string) {
  try { await deletePromptbox(id); msg.success('已删除'); await load() }
  catch (e: any) { msg.error('删除失败：' + e.message) }
}

function goPromptbox() { router.push('/promptbox') }
</script>

<template>
  <div style="margin-bottom:12px;display:flex;align-items:center;gap:12px;flex-wrap:wrap">
    <n-input :value="keyword" placeholder="搜索标题或提示词" size="small" clearable
             @update:value="(v: string) => keyword = v"
             style="min-width:240px;max-width:360px" />
    <n-button size="small" type="primary" @click="goPromptbox">→ 去提示词收藏（上传反推 / 拆分）</n-button>
  </div>
  <n-empty v-if="!filtered.length" :description="keyword ? '没有符合条件的收藏' : '还没有收藏，去提示词收藏页创建'" />
  <n-grid v-else cols="2 600:3 900:4 1200:5" :x-gap="12" :y-gap="12">
    <n-grid-item v-for="it in filtered" :key="it.id">
      <n-card size="small" hoverable>
        <div class="title">{{ it.title || '(未命名)' }}</div>
        <div class="prompt">{{ it.raw_prompt || '(无提示词)' }}</div>
        <n-space v-if="it.image_names.length" style="margin-top:6px">
          <n-image v-for="name in it.image_names.slice(0, 3)" :key="name" width="60"
                   :src="promptboxImageUrl(it.id, name)" object-fit="cover" preview-disabled />
        </n-space>
        <div class="cats">
          <n-tag v-for="k in ORDER" :key="k" size="tiny" round :bordered="false"
                 :type="catCount(it, k) ? 'info' : 'default'">
            {{ TITLES[k] }} {{ catCount(it, k) }}
          </n-tag>
        </div>
        <template #action>
          <n-popconfirm @positive-click="doDelete(it.id)">
            <template #trigger><n-button size="tiny" type="error">删除</n-button></template>
            确认删除？
          </n-popconfirm>
        </template>
      </n-card>
    </n-grid-item>
  </n-grid>
</template>

<style scoped>
.title { font-size: 13px; font-weight: 600 }
.prompt {
  font-size: 12px; color: #666; margin-top: 4px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}
.cats { display: flex; flex-wrap: wrap; gap: 3px; margin-top: 6px }
.cats :deep(.n-tag) { font-size: 11px }
</style>
