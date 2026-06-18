<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NCard, NSpace, NInput, NButton, useMessage } from 'naive-ui'

const msg = useMessage()
const rulesYaml = ref('')
const qualityTags = ref('')

async function load() {
  try {
    const rr = await fetch('/api/config/rules')
    rulesYaml.value = JSON.stringify(await rr.json(), null, 2)
    const q = await fetch('/api/config/quality').then(r => r.json())
    qualityTags.value = (q.tags || []).join(', ')
  } catch (e: any) { msg.error('加载配置失败：' + e.message) }
}
onMounted(load)

async function saveRules() {
  try { JSON.parse(rulesYaml.value) } catch { msg.error('rules 不是合法 JSON'); return }
  // 后端 rules 为只读展示，质量词可写；rules 编辑需 PUT 后端扩展（首版仅质量词可保存）
  msg.info('词表展示为只读，修改请编辑 backend/config/tag_rules.yaml 后重启')
}
async function saveQuality() {
  try {
    const tags = qualityTags.value.split(/[,，]/).map(s => s.trim()).filter(Boolean)
    await fetch('/api/config/quality', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tags }) })
    msg.success('质量词已保存（新反推生效）')
  } catch (e: any) { msg.error('保存失败：' + e.message) }
}
</script>

<template>
  <n-space vertical>
    <n-card title="质量词预设模板">
      <n-input v-model:value="qualityTags" type="textarea" :rows="2" placeholder="逗号分隔" />
      <n-button style="margin-top:8px" type="primary" @click="saveQuality">保存质量词</n-button>
    </n-card>
    <n-card title="分类词表（只读预览）">
      <n-input v-model:value="rulesYaml" type="textarea" :rows="16" readonly />
      <n-button style="margin-top:8px" @click="saveRules">只读说明</n-button>
    </n-card>
  </n-space>
</template>
