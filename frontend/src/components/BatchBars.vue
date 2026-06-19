<script setup lang="ts">
import { computed } from 'vue'
import { NProgress } from 'naive-ui'
const props = defineProps<{ uploaded: number; tagged: number; total: number }>()
const pc = (n: number) => (props.total ? Math.round(n * 100 / props.total) : 0)
const upPct = computed(() => pc(props.uploaded))
const tagPct = computed(() => pc(props.tagged))
</script>

<template>
  <div>
    <div style="margin-bottom:6px">
      <div style="font-size:12px">上传 {{ uploaded }}/{{ total }}</div>
      <n-progress :percentage="upPct" :height="10" />
    </div>
    <div>
      <div style="font-size:12px">反推 {{ tagged }}/{{ total }}</div>
      <n-progress :percentage="tagPct" :height="10" status="success" />
    </div>
  </div>
</template>
