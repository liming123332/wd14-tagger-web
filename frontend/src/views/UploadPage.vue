<script setup lang="ts">
import { ref } from 'vue'
import { NUpload, NButton, NSlider, NSwitch, NSpace, NCard, NDynamicTags, useMessage } from 'naive-ui'
import { useRouter } from 'vue-router'
import { useBatch } from '../composables/useBatch'
import BatchBars from '../components/BatchBars.vue'

const router = useRouter()
const msg = useMessage()
const { state, isBusy, start } = useBatch()
const genTh = ref(0.35)
const charTh = ref(0.9)
const autoTag = ref(true)
const pending = ref<File[]>([])
// 本批图片统一打上的自定义标签（上传时带给每张图）
const pendingTags = ref<string[]>([])
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
      <n-space>
        <div>通用阈值 <n-slider v-model:value="genTh" :min="0" :max="1" :step="0.01" style="width:160px" /> {{ genTh }}</div>
        <div>角色阈值 <n-slider v-model:value="charTh" :min="0" :max="1" :step="0.01" style="width:160px" /> {{ charTh }}</div>
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
      <div v-if="state.phase === 'done'" style="color:#18a058;margin-top:8px">✓ 完成（成功 {{ state.tagged }} · 失败 {{ state.failed }}）</div>
      <div v-if="state.phase === 'error'" style="color:#d03050;margin-top:8px">全部上传失败</div>
      <div v-if="isBusy()" style="font-size:12px;color:#888;margin-top:6px">处理中：{{ state.current }}</div>
    </n-card>
  </n-space>
</template>
