<script setup lang="ts">
import { computed } from 'vue'
import { NCard, NImage, NButton, NTag, useMessage } from 'naive-ui'
import { useRouter } from 'vue-router'
import { fileUrl } from '../api/client'
import { IconCopy, IconDownload, IconStar } from '../components/icons'

// 通用化：cf 列表（角色/艺术家）与图库共用本卡片。所有覆盖字段为可选，
// 不传时回退到图库 item 的原字段，保证 <ImageCard :item="it" /> 行为完全不变。
const props = withDefaults(defineProps<{
  item: any
  to?: string
  imgSrc?: string
  titleText?: string
  tagsList?: string[]
  copyText?: string
  downloadSrc?: string
  downloadName?: string
  // null 哨兵：默认值显式为 null，以便区分「未传」与 favorite:false。
  // （Vue 的 Boolean 类型会把 undefined 强转为 false，无法区分这两种情况。）
  favorite?: boolean | null
}>(), { favorite: null })
const emit = defineEmits<{ (e: 'toggle-favorite'): void }>()

const router = useRouter()
const msg = useMessage()

const dest = computed(() => props.to ?? '/detail/' + props.item.id)
const src = computed(() => props.imgSrc ?? fileUrl(props.item.id, props.item.thumb))
const title = computed(() => props.titleText ?? props.item.source_name)
const tags = computed<any[]>(() => props.tagsList ?? props.item.tags ?? [])
const promptForCopy = computed(() => props.copyText ?? props.item.prompt)
const dlSrc = computed(() => props.downloadSrc ?? fileUrl(props.item.id, props.item.original))
const dlName = computed(() => props.downloadName ?? props.item.source_name)
const showFav = computed(() => props.favorite !== null)

// 卡片只显示前 3 个标签 + 「+N」，避免标签过多撑高卡片
const showTags = computed(() => tags.value.slice(0, 3))
const moreCount = computed(() => Math.max(0, tags.value.length - 3))

function open() { router.push(dest.value) }

async function copy() {
  const p = promptForCopy.value || ''
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
  a.href = dlSrc.value
  a.download = dlName.value
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}
</script>

<template>
  <n-card size="small" class="card">
    <div class="thumb" @click="open">
      <n-image :src="src" object-fit="contain" preview-disabled />
      <div class="actions">
        <n-button size="tiny" circle secondary @click.stop="copy" title="复制完整 prompt"><IconCopy/></n-button>
        <n-button size="tiny" circle secondary @click.stop="download" title="下载原图"><IconDownload/></n-button>
      </div>
      <n-button v-if="showFav" size="tiny" circle class="fav-btn"
                :type="favorite ? 'warning' : 'default'"
                @click.stop="emit('toggle-favorite')" title="收藏"><IconStar/></n-button>
    </div>
    <div class="name">{{ title }}</div>
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
.fav-btn { position: absolute; right: 6px; top: 6px; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.45) }
.name {
  font-size: 12px; margin-top: 4px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.tags { display: flex; flex-wrap: wrap; gap: 3px; margin-top: 4px }
.tags :deep(.n-tag) { font-size: 11px }
.card { transition: transform .2s ease, box-shadow .2s ease }
.card:hover { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(0, 0, 0, 0.12) }
.actions :deep(.n-button) { color: inherit }
/* 卡片缩略图固定 160px 高，img 填满容器并 contain 居中。height:auto 会让
   竖图按比例撑高溢出卡片（那套只适合详情页自适应大图，不适合固定高度卡片） */
:deep(.n-image) { display: block; width: 100%; height: 160px }
:deep(.n-image img) { width: 100%; height: 100%; object-fit: contain; display: block }
</style>
