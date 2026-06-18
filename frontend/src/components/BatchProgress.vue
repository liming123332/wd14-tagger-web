<script setup lang="ts">
import { ref, watch } from 'vue'
import { NProgress, NText } from 'naive-ui'
import { subscribeBatch } from '../api/client'

const props = defineProps<{ batchId: string | null; total: number }>()
const emit = defineEmits<{ (e: 'done'): void }>()

const done = ref(0)
const failed = ref(0)
const current = ref('')
const finished = ref(false)

watch(() => props.batchId, (id) => {
  if (!id) return
  subscribeBatch(id, (ev) => {
    if (ev.type === 'progress') { done.value = ev.done; current.value = ev.current }
    else if (ev.type === 'error') { failed.value++ }
    else if (ev.type === 'done') { finished.value = true; emit('done') }
  })
})
</script>

<template>
  <div v-if="props.batchId">
    <n-progress :percentage="props.total ? Math.round(done * 100 / props.total) : 0" />
    <n-text>{{ done }}/{{ props.total }} 处理中：{{ current }}（失败 {{ failed }}）</n-text>
    <n-text v-if="finished" type="success">　完成</n-text>
  </div>
</template>
