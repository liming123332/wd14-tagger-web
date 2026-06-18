<script setup lang="ts">
import { ref } from 'vue'
import { NUpload, NButton, NSlider, NSwitch, NSpace, NCard, useMessage } from 'naive-ui'
import { useRouter } from 'vue-router'
import { uploadImages, startBatch } from '../api/client'
import BatchProgress from '../components/BatchProgress.vue'

const router = useRouter()
const msg = useMessage()
const genTh = ref(0.35)
const charTh = ref(0.9)
const autoTag = ref(true)
const pending = ref<File[]>([])
const batchId = ref<string | null>(null)
const total = ref(0)

function onSelect(opts: any) { pending.value = opts.fileList.map((f: any) => f.file) }

async function go() {
  if (!pending.value.length) { msg.warning('请先选择图片'); return }
  try {
    const res = await uploadImages(pending.value)
    if (autoTag.value && res.ids.length) {
      total.value = res.ids.length
      const b = await startBatch(res.ids, genTh.value, charTh.value)
      batchId.value = b.batch_id
    } else {
      msg.success('上传完成')
    }
  } catch (e: any) { msg.error('上传失败：' + e.message) }
}
</script>

<template>
  <n-space vertical>
    <n-card title="上传图片">
      <n-upload multiple :default-upload="false" @change="onSelect" accept="image/*">
        <n-button>选择图片（可多选）</n-button>
      </n-upload>
    </n-card>
    <n-card title="反推设置">
      <n-space>
        <div>通用阈值 <n-slider v-model:value="genTh" :min="0" :max="1" :step="0.01" style="width:160px" /> {{ genTh }}</div>
        <div>角色阈值 <n-slider v-model:value="charTh" :min="0" :max="1" :step="0.01" style="width:160px" /> {{ charTh }}</div>
        <div>上传后自动反推 <n-switch v-model:value="autoTag" /></div>
      </n-space>
      <n-space style="margin-top:12px">
        <n-button type="primary" @click="go">开始</n-button>
        <n-button @click="router.push('/gallery')">前往图库</n-button>
      </n-space>
    </n-card>
    <BatchProgress :batch-id="batchId" :total="total" @done="msg.success('批量完成')" />
  </n-space>
</template>
