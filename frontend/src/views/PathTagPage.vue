<script setup lang="ts">
import { ref, computed, onMounted, watch, h } from 'vue'
import { NButton, NSlider, NSpace, NCard, NSelect, NTag, NInput, NCheckbox, useMessage } from 'naive-ui'
import { useTagger } from '../composables/useTagger'
import { usePathTag } from '../composables/usePathTag'
import { IconCheck } from '../components/icons'

const msg = useMessage()
const tagger = useTagger()
const { state, isBusy, start, reset } = usePathTag()

const path = ref('')
const genTh = ref(0.55)
const charTh = ref(0.55)
const recursive = ref(false)
const onConflict = ref<'overwrite' | 'skip'>('overwrite')

const taggerOptions = computed(() => tagger.state.taggers.map(t => ({
  label: t.label, value: t.key, downloaded: t.downloaded,
})))
// naive-ui NSelect 的 render-label 是 prop（非插槽），签名 (option, isSelected) => VNodeChild，
// 同时渲染面板项与 trigger，故已选模型的状态标签在关闭态也显示。与 UploadPage 一致。
function renderTaggerLabel(option: any) {
  return h('span', { style: 'display:inline-flex;align-items:center;gap:6px' }, [
    option.label as any,
    option.downloaded
      ? h(NTag, { type: 'success', size: 'small', bordered: false }, { default: () => '已下载' })
      : h(NTag, { size: 'small', bordered: false }, { default: () => '未下载' }),
  ])
}
const selectedDownloaded = computed(() => tagger.isDownloaded(tagger.state.selected))
onMounted(() => { tagger.refresh() })
async function doDownload() {
  try { await tagger.download(tagger.state.selected); msg.success('下载完成') }
  catch (e: any) { msg.error('下载失败：' + e.message) }
}

const isCl = computed(() => tagger.state.selected === 'cl_tagger')
const charLabel = computed(() => isCl.value ? '角色名称识别阈值（仅 cl_tagger 生效）' : '角色阈值')
// 按模型调默认阈值：v2→0.55/0.55（单阈值），cl_tagger→0.35/0.6，其余→0.35/0.9。
watch(() => tagger.state.selected, (m) => {
  if (m === 'cl_tagger_v2') { genTh.value = 0.55; charTh.value = 0.55 }
  else { genTh.value = 0.35; charTh.value = isCl.value ? 0.6 : 0.9 }
}, { immediate: true })

const conflictOptions = [
  { label: '覆盖已有 txt', value: 'overwrite' },
  { label: '跳过已有 txt', value: 'skip' },
]

async function go() {
  if (!path.value.trim()) { msg.warning('请输入文件夹路径'); return }
  if (isBusy()) { msg.warning('当前任务处理中，请等待完成'); return }
  if (!selectedDownloaded.value) { msg.warning('所选模型未下载'); return }
  try {
    await start({
      path: path.value.trim(), model: tagger.state.selected,
      genTh: genTh.value, charTh: charTh.value, useChar: true,
      recursive: recursive.value, onConflict: onConflict.value,
    })
    msg.success('已提交处理')
  } catch (e: any) { msg.error('提交失败：' + e.message) }
}
</script>

<template>
  <n-space vertical>
    <n-card title="路径打标">
      <div style="margin-bottom:12px">
        <div style="font-size:13px;margin-bottom:4px">文件夹路径（读取该路径下所有图片，生成同名 .txt）</div>
        <n-input v-model:value="path" placeholder="例如 I:/images/folder" :disabled="isBusy()" />
      </div>
      <div style="margin-bottom:12px">
        <div style="font-size:13px;margin-bottom:4px">反推模型</div>
        <n-select
          :value="tagger.state.selected"
          :options="taggerOptions"
          :render-label="renderTaggerLabel"
          @update:value="tagger.setSelected"
          :disabled="isBusy()"
          style="max-width:280px"
        />
        <div v-if="!selectedDownloaded" style="margin-top:6px;display:flex;align-items:center;gap:8px">
          <span style="font-size:12px;color:#d03050">{{ tagger.state.taggers.find(t=>t.key===tagger.state.selected)?.label || tagger.state.selected }} 未下载</span>
          <n-button size="tiny" :loading="tagger.state.downloading===tagger.state.selected" @click="doDownload">下载</n-button>
        </div>
      </div>
      <n-space>
        <div>通用阈值 <n-slider v-model:value="genTh" :min="0" :max="1" :step="0.01" :disabled="isBusy()" style="width:160px" /> {{ genTh }}</div>
        <!-- v2 单阈值不区分角色阈值：隐藏角色滑块（charTh 仍传，后端忽略） -->
        <div v-if="tagger.state.selected !== 'cl_tagger_v2'">{{ charLabel }} <n-slider v-model:value="charTh" :min="0" :max="1" :step="0.01" :disabled="isBusy()" style="width:160px" /> {{ charTh }}</div>
      </n-space>
      <n-space style="margin-top:12px" align="center">
        <n-checkbox v-model:checked="recursive" :disabled="isBusy()">包含子文件夹</n-checkbox>
        <div style="display:flex;align-items:center;gap:8px">
          同名 txt 已存在
          <n-select v-model:value="onConflict" :options="conflictOptions" :disabled="isBusy()" size="small" style="width:160px" />
        </div>
      </n-space>
      <n-space style="margin-top:12px">
        <n-button data-testid="start-btn" type="primary" :disabled="isBusy() || !selectedDownloaded" @click="go">开始</n-button>
        <n-button v-if="state.phase !== 'idle'" :disabled="isBusy()" @click="reset">重置</n-button>
      </n-space>
    </n-card>
    <n-card v-if="state.phase !== 'idle'" title="进度">
      <div>
        {{ state.done }} / {{ state.total }}
        <span style="font-size:12px;color:#888;margin-left:8px">成功 {{ state.ok }} · 跳过 {{ state.skipped }} · 失败 {{ state.failed }}</span>
      </div>
      <div v-if="isBusy()" style="font-size:12px;color:#888;margin-top:6px">处理中：{{ state.current }}</div>
      <div v-if="state.phase === 'done'" style="color:#18a058;margin-top:8px"><IconCheck /> 完成</div>
      <div v-if="state.phase === 'error'" style="color:#d03050;margin-top:8px">任务出错或连接中断</div>
      <div v-if="state.errors.length" style="margin-top:8px">
        <div style="font-size:13px;margin-bottom:4px">失败文件</div>
        <div v-for="(e, i) in state.errors" :key="i" style="font-size:12px;color:#d03050">{{ e.current }}：{{ e.message }}</div>
      </div>
    </n-card>
  </n-space>
</template>
