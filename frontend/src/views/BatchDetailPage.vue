<script setup lang="ts">
import { computed } from 'vue'
import { NCard, NTag, NTable } from 'naive-ui'
import { useBatch } from '../composables/useBatch'
import BatchBars from '../components/BatchBars.vue'

const { state } = useBatch()
const doneCount = computed(() => state.tagged + state.failed)
function tagType(s: string) { return s === 'ok' ? 'success' : s === 'error' ? 'error' : 'default' }
function tagText(s: string) { return s === 'ok' ? '完成' : s === 'error' ? '失败' : '待处理' }
</script>

<template>
  <n-card title="批量处理详情">
    <div style="margin-bottom:12px">
      已完成 {{ doneCount }}/{{ state.total }}（成功 {{ state.tagged }} · 失败 {{ state.failed }}）
    </div>
    <BatchBars :uploaded="state.uploaded" :tagged="state.tagged" :total="state.total" />
    <n-table :bordered="false" :single-line="false" style="margin-top:12px">
      <thead><tr><th>文件名</th><th>状态</th><th>说明</th></tr></thead>
      <tbody>
        <tr v-for="it in state.items" :key="it.id || it.name">
          <td>{{ it.name }}</td>
          <td><n-tag :type="tagType(it.status)" size="small">{{ tagText(it.status) }}</n-tag></td>
          <td>{{ it.msg || '' }}</td>
        </tr>
      </tbody>
    </n-table>
  </n-card>
</template>
