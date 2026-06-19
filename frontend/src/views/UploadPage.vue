<script setup lang="ts">
import { ref, computed, onMounted, watch, h } from 'vue'
import { NUpload, NButton, NSlider, NSwitch, NSpace, NCard, NDynamicTags, useMessage } from 'naive-ui'
import { NSelect, NTag } from 'naive-ui'
import { useTagger } from '../composables/useTagger'
import { useRouter } from 'vue-router'
import { useBatch } from '../composables/useBatch'
import BatchBars from '../components/BatchBars.vue'
import { IconCheck } from '../components/icons'

const router = useRouter()
const msg = useMessage()
const { state, isBusy, start } = useBatch()
const genTh = ref(0.35)
const charTh = ref(0.9)
const autoTag = ref(true)
const pending = ref<File[]>([])
// 本批图片统一打上的自定义标签（上传时带给每张图）
const pendingTags = ref<string[]>([])
const tagger = useTagger()
const taggerOptions = computed(() => tagger.state.taggers.map(t => ({
  label: t.label, value: t.key, downloaded: t.downloaded,
})))
// naive-ui NSelect 的 render-label 是 prop（render function），不是插槽（v2.44 SelectSlots
// 未声明 renderLabel，运行时走 props.renderLabel）。签名 (option, isSelected) => VNodeChild，
// 同时渲染面板项与 trigger，故已选模型的状态标签在关闭态也显示。
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
// cl_tagger 角色名称识别阈值默认 0.6（移植 mikazuki character_threshold），其余模型 0.9。
// 标签体现「仅 cl_tagger 生效」（cl 专门训练角色/版权识别，阈值与文案单独区分）。
const isCl = computed(() => tagger.state.selected === 'cl_tagger')
const charLabel = computed(() => isCl.value ? '角色名称识别阈值（仅 cl_tagger 生效）' : '角色阈值')
watch(() => tagger.state.selected, () => { charTh.value = isCl.value ? 0.6 : 0.9 }, { immediate: true })
// n-upload 受控文件列表：关掉默认列表后用 v-model 受控，便于「清空」重置上传组件内部状态
const fileList = ref<any[]>([])

function onSelect(opts: any) { pending.value = opts.fileList.map((f: any) => f.file) }
function clearSel() { pending.value = []; fileList.value = [] }

async function go() {
  if (!pending.value.length) { msg.warning('请先选择图片'); return }
  if (isBusy()) { msg.warning('当前批次处理中，请等待完成'); return }
  try {
    await start(pending.value, autoTag.value, genTh.value, charTh.value, pendingTags.value)
    pending.value = []
    fileList.value = []
    pendingTags.value = []
    msg.success('已提交处理')
  } catch (e: any) { msg.error('提交失败：' + e.message) }
}
</script>

<template>
  <n-space vertical>
    <n-card title="上传图片">
      <n-upload multiple :default-upload="false" :show-file-list="false" :disabled="isBusy()"
                v-model:file-list="fileList" @change="onSelect" accept="image/*">
        <n-button :disabled="isBusy()">选择图片（可多选）</n-button>
      </n-upload>
      <!-- 关掉默认文件名列表后用紧凑汇总条代替：只显示已选数量+清空，避免选几十张撑满页面 -->
      <div v-if="pending.length" style="margin-top:10px;display:flex;align-items:center;gap:12px">
        <span style="font-size:13px">已选 {{ pending.length }} 张</span>
        <n-button size="tiny" :disabled="isBusy()" @click="clearSel">清空</n-button>
      </div>
    </n-card>
    <n-card title="反推设置">
      <div style="margin-bottom:12px">
        <div style="font-size:13px;margin-bottom:4px">反推模型</div>
        <n-select
          :value="tagger.state.selected"
          :options="taggerOptions"
          :render-label="renderTaggerLabel"
          @update:value="tagger.setSelected"
          style="max-width:280px"
        />
        <div v-if="!selectedDownloaded" style="margin-top:6px;display:flex;align-items:center;gap:8px">
          <span style="font-size:12px;color:#d03050">{{ tagger.state.taggers.find(t=>t.key===tagger.state.selected)?.label || tagger.state.selected }} 未下载</span>
          <n-button size="tiny" :loading="tagger.state.downloading===tagger.state.selected" @click="doDownload">下载</n-button>
        </div>
      </div>
      <n-space>
        <div>通用阈值 <n-slider v-model:value="genTh" :min="0" :max="1" :step="0.01" style="width:160px" /> {{ genTh }}</div>
        <div>{{ charLabel }} <n-slider v-model:value="charTh" :min="0" :max="1" :step="0.01" style="width:160px" /> {{ charTh }}</div>
        <div>上传后自动反推 <n-switch v-model:value="autoTag" /></div>
      </n-space>
      <div style="margin-top:12px">
        <div style="font-size:13px;margin-bottom:4px">批量标签（给本批所有图打上这些自定义标签，方便图库筛选）</div>
        <n-dynamic-tags v-model:value="pendingTags" />
      </div>
      <n-space style="margin-top:12px">
        <n-button data-testid="start-btn" type="primary" :disabled="isBusy()" @click="go">开始</n-button>
        <n-button v-if="state.batchId" @click="router.push('/batch/' + state.batchId)">查看详情</n-button>
        <n-button @click="router.push('/gallery')">前往图库</n-button>
      </n-space>
    </n-card>
    <n-card v-if="state.phase !== 'idle'" title="进度">
      <BatchBars :uploaded="state.uploaded" :tagged="state.tagged" :total="state.total" />
      <div v-if="state.phase === 'done'" style="color:#18a058;margin-top:8px"><IconCheck/> 完成（成功 {{ state.tagged }} · 失败 {{ state.failed }}）</div>
      <div v-if="state.phase === 'error'" style="color:#d03050;margin-top:8px">全部上传失败</div>
      <div v-if="isBusy()" style="font-size:12px;color:#888;margin-top:6px">处理中：{{ state.current }}</div>
    </n-card>
  </n-space>
</template>
