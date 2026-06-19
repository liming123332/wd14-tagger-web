<script setup lang="ts">
import { useRouter } from 'vue-router'
import { NTag } from 'naive-ui'
import { useBatch } from '../composables/useBatch'

const router = useRouter()
const { state } = useBatch()

function visible() { return state.phase !== 'idle' }
function toDetail() { if (state.batchId) router.push('/batch/' + state.batchId) }
</script>

<template>
  <n-tag v-if="visible()" data-testid="badge"
         :type="state.phase === 'done' ? 'success' : 'info'"
         size="small" checkable
         :style="{ cursor: state.batchId ? 'pointer' : 'default' }"
         @click="toDetail">
    <template v-if="state.phase === 'done'">✓ 完成 {{ state.total }}</template>
    <template v-else>↑{{ state.uploaded }}/{{ state.total }} · ↓{{ state.tagged }}/{{ state.total }}</template>
  </n-tag>
</template>
