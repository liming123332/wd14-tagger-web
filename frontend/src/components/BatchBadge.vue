<script setup lang="ts">
import { useRouter } from 'vue-router'
import { NTag, NIcon } from 'naive-ui'
import { IconCheck, IconUpload as IconUp, IconDownload as IconDl } from './icons'
import { useBatch } from '../composables/useBatch'

const router = useRouter()
const { state } = useBatch()

function visible() { return state.phase !== 'idle' }
function toDetail() { if (state.batchId) router.push('/batch/' + state.batchId) }
</script>

<template>
  <n-tag v-if="visible()" data-testid="badge"
         :type="state.phase === 'done' ? 'success' : 'info'" size="small"
         :style="{ cursor: state.batchId ? 'pointer' : 'default' }" @click="toDetail">
    <template v-if="state.phase === 'done'"><n-icon :component="IconCheck" /> 完成 {{ state.total }}</template>
    <template v-else><n-icon :component="IconUp" /> {{ state.uploaded }}/{{ state.total }} · <n-icon :component="IconDl" /> {{ state.tagged }}/{{ state.total }}</template>
  </n-tag>
</template>
