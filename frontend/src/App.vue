<script setup lang="ts">
import { NConfigProvider, NMessageProvider, NDialogProvider, NLayout, NMenu } from 'naive-ui'
import { useRouter } from 'vue-router'
const router = useRouter()
const options = [
  { label: '上传', key: 'upload' },
  { label: '图库', key: 'gallery' },
  { label: '设置', key: 'settings' },
]
function go(key: string) { router.push('/' + key) }
</script>

<template>
  <n-config-provider>
    <n-message-provider>
      <n-dialog-provider>
        <n-layout style="min-height:100vh">
          <n-menu mode="horizontal" :options="options" @update:value="go" />
          <div style="padding:16px"><router-view /></div>
        </n-layout>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>
