<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NCard, NSpace, NInput, NButton, useMessage } from 'naive-ui'
import { getAnimaToken, setAnimaToken } from '../api/characterfinder'

const msg = useMessage()
const rulesYaml = ref('')
const qualityTags = ref('')
const tokenStatus = ref<{ configured: boolean; preview: string | null }>({ configured: false, preview: null })
const tokenInput = ref('')
const savingToken = ref(false)

async function load() {
  try {
    const rr = await fetch('/api/config/rules')
    rulesYaml.value = JSON.stringify(await rr.json(), null, 2)
    const q = await fetch('/api/config/quality').then(r => r.json())
    qualityTags.value = (q.tags || []).join(', ')
    tokenStatus.value = await getAnimaToken()
  } catch (e: any) { msg.error('加载配置失败：' + e.message) }
}
onMounted(load)

async function saveToken() {
  if (!tokenInput.value.trim()) { msg.warning('请粘贴 token'); return }
  savingToken.value = true
  try {
    const r = await setAnimaToken(tokenInput.value.trim())
    tokenStatus.value = r; tokenInput.value = ''; msg.success('token 已保存')
  } catch (e: any) { msg.error('保存失败：' + e.message) }
  finally { savingToken.value = false }
}

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
    <n-card title="Anima 数据更新 token">
      <div v-if="tokenStatus.configured" style="margin-bottom:8px;font-size:13px;color:#888">
        当前已配置：<code>{{ tokenStatus.preview }}</code>
      </div>
      <div v-else style="margin-bottom:8px;font-size:13px;color:#d03050">
        未配置（双击「更新anima数据.bat」时会在命令行提示输入）
      </div>
      <n-input v-model:value="tokenInput" type="password" placeholder="粘贴 animadex export token" />
      <div style="font-size:12px;color:#888;margin-top:4px;line-height:1.6">
        获取：登录 animadex.net → Account → Offline dataset export → Generate token。<br />
        token 仅存于本地，不外传；失效后在此重新粘贴即可。
      </div>
      <n-button style="margin-top:8px" type="primary" :loading="savingToken" @click="saveToken">保存 token</n-button>
    </n-card>
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
