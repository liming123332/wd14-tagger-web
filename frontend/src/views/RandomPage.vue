<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NGrid, NGridItem, NEmpty, NButton } from 'naive-ui'
import { randomImages } from '../api/client'
import { IconRandom } from '../components/icons'
import ImageCard from '../components/ImageCard.vue'

const items = ref<any[]>([])
const size = 24
const loading = ref(false)

async function shuffle() {
  loading.value = true
  try {
    const r = await randomImages(size)
    items.value = r.items
  } finally {
    loading.value = false
  }
}
onMounted(shuffle)
</script>

<template>
  <div style="margin-bottom:12px">
    <n-button type="primary" size="small" :loading="loading" @click="shuffle"><IconRandom/> 再抽一页</n-button>
    <span style="font-size:12px;color:#888;margin-left:8px">从全库随机展示 {{ size }} 张</span>
  </div>
  <n-empty v-if="!items.length" description="图库还没有图片，先去上传" />
  <n-grid v-else cols="2 600:3 900:5 1200:6" :x-gap="12" :y-gap="12">
    <n-grid-item v-for="it in items" :key="it.id">
      <ImageCard :item="it" />
    </n-grid-item>
  </n-grid>
</template>
