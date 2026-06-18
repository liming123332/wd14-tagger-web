<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NGrid, NGridItem, NCard, NImage, NPagination, NEmpty } from 'naive-ui'
import { useRouter } from 'vue-router'
import { listImages, fileUrl } from '../api/client'

const router = useRouter()
const items = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const size = 24

async function load() {
  const r = await listImages(page.value, size)
  items.value = r.items; total.value = r.total
}
onMounted(load)

function open(id: string) { router.push('/detail/' + id) }
</script>

<template>
  <n-empty v-if="!items.length" description="还没有图片，先去上传" />
  <n-grid v-else cols="2 600:3 900:5 1200:6" :x-gap="12" :y-gap="12">
    <n-grid-item v-for="it in items" :key="it.id">
      <n-card size="small" hoverable @click="open(it.id)">
        <n-image :src="fileUrl(it.id, it.thumb)" object-fit="contain"
                 style="height:160px;width:100%" preview-disabled />
        <div style="font-size:12px;margin-top:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
          {{ it.source_name }}
        </div>
      </n-card>
    </n-grid-item>
  </n-grid>
  <n-pagination v-if="total > size" v-model:page="page" :item-count="total"
                :page-size="size" @update:page="load" style="margin-top:16px" />
</template>
