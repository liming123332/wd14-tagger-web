<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { NCard, NSpace, NInput, NButton, NSwitch, NTag, useMessage } from 'naive-ui'
import { getAnimaToken, setAnimaToken } from '../api/characterfinder'
import { useTranslator } from '../composables/useTranslator'

const msg = useMessage()
const translator = useTranslator()
const unloadingT = ref(false)
const forceCpu = ref(false)
const savingDevice = ref(false)
const rulesYaml = ref('')
const qualityTags = ref('')
const tokenStatus = ref<{ configured: boolean; preview: string | null }>({ configured: false, preview: null })
const tokenInput = ref('')
const savingToken = ref(false)
const dataDir = ref<{ current: string; configured: string | null; source: string }>({ current: '', configured: null, source: 'default' })
const dataDirInput = ref('')
const savingDataDir = ref(false)
const resettingDataDir = ref(false)
const sourceLabel = computed(() => {
  const m: Record<string, string> = { env: '环境变量', page: '页面配置', default: '默认' }
  return m[dataDir.value.source] || dataDir.value.source
})
const sourceTagType = computed<'warning' | 'info' | 'default'>(() =>
  dataDir.value.source === 'env' ? 'warning' : dataDir.value.source === 'page' ? 'info' : 'default'
)

async function load() {
  try {
    const rr = await fetch('/api/config/rules')
    rulesYaml.value = JSON.stringify(await rr.json(), null, 2)
    const q = await fetch('/api/config/quality').then(r => r.json())
    qualityTags.value = (q.tags || []).join(', ')
    tokenStatus.value = await getAnimaToken()
    const dev = await fetch('/api/config/device').then(r => r.json())
    forceCpu.value = !!dev.force_cpu
    const dd = await fetch('/api/config/data-dir').then(r => r.json())
    dataDir.value = dd
    dataDirInput.value = dd.configured ?? dd.current
  } catch (e: any) { msg.error('加载配置失败：' + e.message) }
  translator.refreshStatus()  // 翻译模型下载/加载状态（不阻塞主配置加载）
}
onMounted(load)

async function onToggleDevice(v: boolean) {
  savingDevice.value = true
  try {
    const r = await fetch('/api/config/device', {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ force_cpu: v })
    }).then(r => r.json())
    forceCpu.value = r.force_cpu
    msg.success(v ? '已切换为 CPU 反推（已加载的反推模型将重新加载）' : '已切换为自动 GPU 反推（已加载的反推模型将重新加载）')
  } catch (e: any) {
    msg.error('切换失败：' + e.message)
    forceCpu.value = !v  // 失败回滚开关状态
  } finally { savingDevice.value = false }
}

async function saveToken() {
  if (!tokenInput.value.trim()) { msg.warning('请粘贴 token'); return }
  savingToken.value = true
  try {
    const r = await setAnimaToken(tokenInput.value.trim())
    tokenStatus.value = r; tokenInput.value = ''; msg.success('token 已保存')
  } catch (e: any) { msg.error('保存失败：' + e.message) }
  finally { savingToken.value = false }
}

async function saveDataDir() {
  const p = dataDirInput.value.trim()
  if (!p) { msg.warning('请填写目录路径'); return }
  savingDataDir.value = true
  try {
    const r = await fetch('/api/config/data-dir', {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: p })
    })
    if (!r.ok) {
      const e = await r.json().catch(() => ({}))
      throw new Error(e.detail || `HTTP ${r.status}`)
    }
    const j = await r.json()
    dataDir.value.configured = j.configured
    msg.success('已保存，重启后端生效：关闭黑窗重新双击 启动.bat')
  } catch (e: any) { msg.error('保存失败：' + e.message) }
  finally { savingDataDir.value = false }
}

async function resetDataDir() {
  resettingDataDir.value = true
  try {
    await fetch('/api/config/data-dir', { method: 'DELETE' })
    dataDir.value.configured = null
    dataDirInput.value = dataDir.value.current
    msg.success('已清除页面配置，重启后端生效')
  } catch (e: any) { msg.error('清除失败：' + e.message) }
  finally { resettingDataDir.value = false }
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

// 翻译模型：手动下载 / 卸载（首次翻译时也会自动触发下载，这里给一个集中入口）
async function doDlTranslate() {
  try { await translator.download(); msg.success('翻译模型下载完成') }
  catch (e: any) { msg.error('下载失败：' + e.message) }
}
async function onUnloadT() {
  unloadingT.value = true
  try { await translator.unload(); msg.success('已释放翻译模型（下次翻译重新加载）') }
  catch (e: any) { msg.error('卸载失败：' + e.message) }
  finally { unloadingT.value = false }
}
</script>

<template>
  <n-space vertical>
    <n-card title="数据目录">
      <div style="font-size:13px;margin-bottom:8px">
        当前：<code>{{ dataDir.current }}</code>
        <n-tag :type="sourceTagType" size="small" style="margin-left:8px">{{ sourceLabel }}</n-tag>
      </div>
      <n-input v-model:value="dataDirInput" :disabled="dataDir.source === 'env'"
        placeholder="如 D:\tagger-data 或 \\Z4-eydz\135xxxx4048\wd14\data" />
      <div v-if="dataDir.source === 'env'" style="font-size:12px;color:#d03050;margin-top:6px;line-height:1.6">
        环境变量 WD14_DATA_DIR 已设置，优先于本配置；如需在此配置请先清除该环境变量。
      </div>
      <div v-else style="font-size:12px;color:#888;margin-top:6px;line-height:1.6">
        支持本地盘（如 <code>D:\tagger-data</code>）与 NAS UNC 路径（如 <code>\\Z4-eydz\135xxxx4048\wd14\data</code>）。<br />
        NAS 需当前 Windows 账户对该共享有读写权限（带密码共享先 <code>net use</code> 或存入凭据管理器）。<br />
        切换后旧数据不会自动迁移，需手动复制或重新生成。
      </div>
      <n-space style="margin-top:8px">
        <n-button type="primary" :loading="savingDataDir" :disabled="dataDir.source === 'env'" @click="saveDataDir">保存</n-button>
        <n-button :loading="resettingDataDir" :disabled="!dataDir.configured" @click="resetDataDir">恢复默认</n-button>
      </n-space>
    </n-card>
    <n-card title="反推设备">
      <n-space align="center">
        <n-switch :value="forceCpu" :loading="savingDevice" @update:value="onToggleDevice" />
        <span style="font-size:14px">{{ forceCpu ? '强制 CPU' : '自动（GPU 优先）' }}</span>
      </n-space>
      <div style="font-size:12px;color:#888;margin-top:8px;line-height:1.6">
        开启后反推（打标）强制用 CPU、不占 GPU 显存；关闭则自动选用 GPU（CUDA / DirectML）。切换会卸载当前已加载的反推模型，下次反推时按新设备重新加载。
      </div>
    </n-card>
    <n-card title="翻译模型（Hy-MT2 1.8B）">
      <div v-if="translator.state.downloaded" style="font-size:13px;color:#18a058;margin-bottom:8px">
        ✓ 已下载<span v-if="translator.state.loaded">（已加载，可直接翻译）</span> —— 各详情页分类点「翻译本分类」查看中文释义
      </div>
      <div v-else style="font-size:13px;color:#d03050;margin-bottom:8px">
        未下载（GGUF ~0.7GB），首次点「翻译本分类」时自动下载，也可在此手动下载
      </div>
      <n-space>
        <n-button v-if="!translator.state.downloaded" type="primary" :loading="translator.state.downloading" @click="doDlTranslate">下载翻译模型</n-button>
        <n-button v-if="translator.state.loaded" :loading="unloadingT" @click="onUnloadT">卸载（释放显存/内存）</n-button>
      </n-space>
      <div style="font-size:12px;color:#888;margin-top:6px;line-height:1.6">
        腾讯 Hy-MT2-1.8B 多语言翻译模型，本地 GPU 推理（Blackwell CUDA）；翻译结果不存储，每次现译。
      </div>
    </n-card>
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
