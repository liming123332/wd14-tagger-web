<script setup lang="ts">
import { computed } from 'vue'
import { NCard, NImage, NButton, NTag, useMessage } from 'naive-ui'
import { useRouter } from 'vue-router'
import { fileUrl } from '../api/client'

const props = defineProps<{ item: any }>()
const router = useRouter()
const msg = useMessage()

// 卡片只显示前 3 个标签 + 「+N」，避免标签过多撑高卡片
const showTags = computed(() => (props.item.tags || []).slice(0, 3))
const moreCount = computed(() => Math.max(0, (props.item.tags || []).length - 3))

function open() { router.push('/detail/' + props.item.id) }

async function copy() {
  const p = props.item.prompt || ''
  if (!p) { msg.warning('该图尚未反推'); return }
  try {
    await navigator.clipboard.writeText(p)
    msg.success('已复制 prompt')
  } catch {
    msg.error('复制失败')
  }
}

function download() {
  // 用 JS 触发 <a download>，避免依赖 n-button 的 tag 透传，同源下强制下载
  const a = document.createElement('a')
  a.href = fileUrl(props.item.id, props.item.original)
  a.download = props.item.source_name
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}
</script>

<template>
  <n-card size="small" hoverable>
    <div class="thumb" @click="open">
      <n-image :src="fileUrl(item.id, item.thumb)" object-fit="contain" preview-disabled />
      <div class="actions">
        <n-button size="tiny" circle secondary @click.stop="copy" title="复制完整 prompt">📋</n-button>
        <n-button size="tiny" circle secondary @click.stop="download" title="下载原图">⬇</n-button>
      </div>
    </div>
    <div class="name">{{ item.source_name }}</div>
    <div v-if="showTags.length" class="tags">
      <n-tag v-for="t in showTags" :key="t" size="tiny" round>{{ t }}</n-tag>
      <n-tag v-if="moreCount" size="tiny" round :bordered="false" type="info">+{{ moreCount }}</n-tag>
    </div>
  </n-card>
</template>

<style scoped>
.thumb { position: relative; cursor: pointer }
.actions { position: absolute; left: 6px; top: 6px; display: flex; gap: 4px }
.actions :deep(.n-button) { box-shadow: 0 2px 6px rgba(0, 0, 0, 0.45) }
.name {
  font-size: 12px; margin-top: 4px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.tags { display: flex; flex-wrap: wrap; gap: 3px; margin-top: 4px }
.tags :deep(.n-tag) { font-size: 11px }
/* 卡片缩略图固定 160px 高，img 填满容器并 contain 居中。height:auto 会让
   竖图按比例撑高溢出卡片（那套只适合详情页自适应大图，不适合固定高度卡片） */
:deep(.n-image) { display: block; width: 100%; height: 160px }
:deep(.n-image img) { width: 100%; height: 100%; object-fit: contain; display: block }
</style>
