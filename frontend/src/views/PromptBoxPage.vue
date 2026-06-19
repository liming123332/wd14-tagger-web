<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import {
  NSpace, NCard, NButton, NInput, NDynamicTags, NUpload, NImage, NPopconfirm, useMessage,
} from 'naive-ui'
import {
  splitPrompt, listPromptbox, savePromptbox, deletePromptbox, promptboxImageUrl,
  type PromptboxItem,
} from '../api/client'

const msg = useMessage()

const ORDER = ['quality', 'head', 'clothing', 'view', 'action', 'scene'] as const
const TITLES: Record<string, string> = {
  quality: '质量', head: '头部', clothing: '服装', view: '视角', action: '动作', scene: '场景', extras: '未归类',
}

// 工作区
const inputText = ref('')
const categories = ref<Record<string, string[]>>({})
const extras = ref<string[]>([])
const title = ref('')
const exampleFiles = ref<File[]>([])
const splitLoading = ref(false)

// 列表
const items = ref<PromptboxItem[]>([])

function emptyCats(): Record<string, string[]> {
  return { quality: [], head: [], clothing: [], view: [], action: [], scene: [] }
}

async function loadList() {
  try { items.value = await listPromptbox() } catch (e: any) { msg.error('加载失败：' + e.message) }
}
onMounted(loadList)

async function doSplit() {
  if (!inputText.value.trim()) { msg.warning('请先输入提示词'); return }
  splitLoading.value = true
  try {
    const res = await splitPrompt(inputText.value)
    categories.value = { ...emptyCats(), ...res.categories }
    extras.value = res.extras
  } catch (e: any) { msg.error('拆分失败：' + e.message) }
  finally { splitLoading.value = false }
}

const fullPrompt = computed(() =>
  ORDER.map(k => categories.value[k] || []).flat().filter(Boolean).join(', '),
)
async function copyPrompt() {
  try { await navigator.clipboard.writeText(fullPrompt.value); msg.success('已复制完整 prompt') }
  catch (e: any) { msg.error('复制失败：' + e.message) }
}

function onExampleChange(opts: any) {
  exampleFiles.value = (opts.fileList || []).map((f: any) => f.file).filter(Boolean)
}

async function saveAsCollection() {
  const fd = new FormData()
  fd.append('title', title.value)
  fd.append('raw_prompt', inputText.value)
  fd.append('categories', JSON.stringify(categories.value))
  fd.append('extras', JSON.stringify(extras.value))
  for (const f of exampleFiles.value) fd.append('files', f)
  try {
    await savePromptbox(fd)
    msg.success('已保存')
    title.value = ''; exampleFiles.value = []
    await loadList()
  } catch (e: any) { msg.error('保存失败：' + e.message) }
}

function loadIntoWorkspace(it: PromptboxItem) {
  title.value = it.title
  inputText.value = it.raw_prompt
  categories.value = { ...emptyCats(), ...it.categories }
  extras.value = [...it.extras]
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function doDelete(id: string) {
  try { await deletePromptbox(id); msg.success('已删除'); await loadList() }
  catch (e: any) { msg.error('删除失败：' + e.message) }
}
</script>

<template>
  <n-space vertical>
    <n-card title="拆分工作区">
      <n-input v-model:value="inputText" type="textarea" :rows="4" placeholder="粘贴提示词，逗号或换行分隔" />
      <n-space style="margin-top:10px">
        <n-button type="primary" :loading="splitLoading" data-testid="split-btn" @click="doSplit">拆分</n-button>
        <n-button @click="copyPrompt">复制完整 prompt</n-button>
      </n-space>

      <div v-for="k in [...ORDER, 'extras']" :key="k" style="margin-top:12px">
        <div style="font-size:13px;margin-bottom:2px">{{ TITLES[k] }}</div>
        <n-dynamic-tags v-if="k !== 'extras'" v-model:value="categories[k]" />
        <n-dynamic-tags v-else v-model:value="extras" />
      </div>

      <div style="margin-top:14px">
        <n-input v-model:value="title" placeholder="收藏标题（可选）" style="max-width:320px" />
        <div style="margin-top:8px">
          <n-upload multiple :default-upload="false" :show-file-list="false" @change="onExampleChange" accept="image/*">
            <n-button>选择示例图（可多选）</n-button>
          </n-upload>
          <span v-if="exampleFiles.length" style="margin-left:10px;font-size:13px">已选 {{ exampleFiles.length }} 张</span>
        </div>
        <n-button style="margin-top:10px" type="primary" @click="saveAsCollection">另存为收藏</n-button>
      </div>
    </n-card>

    <n-card title="收藏列表">
      <div v-if="!items.length" style="color:#888">暂无收藏</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px">
        <n-card v-for="it in items" :key="it.id" :title="it.title || '(未命名)'">
          <div style="font-size:12px;color:#666;margin-bottom:6px">{{ it.raw_prompt }}</div>
          <n-space v-if="it.image_names.length">
            <n-image v-for="name in it.image_names" :key="name" width="80"
                     :src="promptboxImageUrl(it.id, name)" object-fit="cover" />
          </n-space>
          <template #action>
            <n-space>
              <n-button size="small" @click="loadIntoWorkspace(it)">编辑</n-button>
              <n-popconfirm @positive-click="doDelete(it.id)">
                <template #trigger><n-button size="small" type="error">删除</n-button></template>
                确认删除？
              </n-popconfirm>
            </n-space>
          </template>
        </n-card>
      </div>
    </n-card>
  </n-space>
</template>
