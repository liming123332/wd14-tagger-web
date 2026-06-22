<script setup lang="ts">
import { computed, h } from 'vue'
import {
  NConfigProvider, NMessageProvider, NDialogProvider, NLayout, NLayoutSider,
  NLayoutContent, NMenu, NButton, NIcon, darkTheme,
} from 'naive-ui'
import type { GlobalTheme } from 'naive-ui'
import { useRouter, useRoute } from 'vue-router'
import BatchBadge from './components/BatchBadge.vue'
import { lightOverrides, darkOverrides } from './styles/theme'
import { useTheme } from './composables/useTheme'
import { useTagger } from './composables/useTagger'
import { useTranslator } from './composables/useTranslator'
import {
  IconUpload, IconGallery, IconRandom, IconStar, IconEdit, IconSettings,
  IconSun, IconMoon, IconMonitor, IconFolderTag, IconCharacter, IconArtist, IconBookmark,
} from './components/icons'

const router = useRouter()
const route = useRoute()
const { mode, effective, setMode } = useTheme()
const tagger = useTagger()
const translator = useTranslator()

// 下载进度浮层：tagger / translator 任意在下载即显示。
// _download_util 为单任务模型（同时只有一个下载），故取当前活跃者的 progress 即可。
function human(n: number): string {
  if (n < 1024) return n + 'B'
  let v = n / 1024; let i = 0
  for (const u of ['KB', 'MB', 'GB']) { if (v < 1024 || i === 2) return v.toFixed(1) + u; v /= 1024; i++ }
  return v.toFixed(1) + 'TB'
}
const downloading = computed(() => !!(tagger.state.downloading || translator.state.downloading))
const downloadingLabel = computed(() => tagger.state.downloading || (translator.state.downloading ? '翻译模型' : ''))
const activeProgress = computed(() =>
  tagger.state.downloading ? tagger.state.progress
  : translator.state.downloading ? translator.state.progress
  : null
)
const progressText = computed(() => {
  const p = activeProgress.value
  if (!p) return '准备下载…'
  const pct = p.size ? Math.round(p.downloaded * 100 / p.size) : 0
  const sz = p.size ? `${human(p.downloaded)} / ${human(p.size)}` : human(p.downloaded)
  return `${p.file || '…'} · ${sz} · ${pct}% · 文件 ${p.index + 1}/${p.total_files}`
})
const progressPct = computed(() => {
  const p = activeProgress.value
  if (!p || !p.size) return 0
  return Math.min(100, Math.round(p.downloaded * 100 / p.size))
})

const theme = computed<GlobalTheme | null>(() => (effective.value === 'dark' ? darkTheme : null))
const overrides = computed(() => (effective.value === 'dark' ? darkOverrides : lightOverrides))

const ITEMS = [
  { label: '上传', key: '/upload', icon: IconUpload },
  { label: '路径打标', key: '/pathtag', icon: IconFolderTag },
  { label: '图库', key: '/gallery', icon: IconGallery },
  { label: '角色图鉴', key: '/characters', icon: IconCharacter },
  { label: '艺术家', key: '/artists', icon: IconArtist },
  { label: 'cf 收藏', key: '/cf/favorites', icon: IconBookmark },
  { label: '随机', key: '/random', icon: IconRandom },
  { label: '收藏列表', key: '/collections', icon: IconStar },
  { label: '提示词收藏', key: '/promptbox', icon: IconEdit },
  { label: '设置', key: '/settings', icon: IconSettings },
] as const

const menuOptions = ITEMS.map(it => ({
  label: it.label, key: it.key,
  icon: () => h(NIcon, { component: it.icon }),
}))
const activeKey = computed(() => {
  const path = route.path
  const hit = ITEMS.map(i => i.key).filter(k => path.startsWith(k))
    .sort((a, b) => b.length - a.length)[0]
  return hit || '/gallery'
})
function go(key: string) { router.push(key) }

const currentTitle = computed(() => {
  const p = route.path
  if (p.startsWith('/detail')) return '图片详情'
  if (p.startsWith('/batch')) return '批次详情'
  return ITEMS.find(i => i.key === activeKey.value)?.label || ''
})

const themeIcon = computed(() =>
  mode.value === 'light' ? IconSun : mode.value === 'dark' ? IconMoon : IconMonitor)
const themeLabel = computed(() => mode.value === 'auto' ? '自动' : mode.value === 'light' ? '浅色' : '深色')
function cycleTheme() {
  const order = ['auto', 'light', 'dark'] as const
  setMode(order[(order.indexOf(mode.value) + 1) % order.length])
}
</script>

<template>
  <n-config-provider :theme="theme" :theme-overrides="overrides">
    <n-message-provider>
      <n-dialog-provider>
        <n-layout has-sider :class="effective" style="min-height:100vh">
          <n-layout-sider class="sider" bordered :width="220" :collapsed-width="64" show-trigger collapse-mode="width"
                          :native-scrollbar="false"
                          content-style="display:flex;flex-direction:column;min-height:100%">
            <div class="brand">WD14 标注</div>
            <n-menu :value="activeKey" :options="menuOptions" :collapsed-width="64"
                    @update:value="go" style="flex:1" />
            <div class="sider-foot">
              <n-button quaternary size="small" block @click="cycleTheme">
                <template #icon><n-icon :component="themeIcon" /></template>
                {{ themeLabel }}
              </n-button>
            </div>
          </n-layout-sider>
          <n-layout-content :native-scrollbar="false">
            <div class="topbar">
              <span class="title">{{ currentTitle }}</span>
              <BatchBadge />
            </div>
            <div class="content">
              <router-view v-slot="{ Component }">
                <transition name="fade" mode="out-in">
                  <div :key="route.path" class="route-view">
                    <component :is="Component" />
                  </div>
                </transition>
              </router-view>
            </div>
          </n-layout-content>
        </n-layout>
        <!-- 全局下载进度浮层（任意页面点下载都显示） -->
        <div v-if="downloading" class="dl-bar">
          <div class="dl-head">
            <span class="dl-title">下载模型 {{ downloadingLabel }}</span>
            <span class="dl-text">{{ progressText }}</span>
          </div>
          <div class="dl-track"><div class="dl-fill" :style="{ width: progressPct + '%' }"></div></div>
        </div>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<style scoped>
/* 侧栏固定视口高：避免被 n-layout 的 align-stretch 拉到主内容高度，
   导致底部主题钮位置随页签内容长短漂移（短页在视口内、长页需滚到底）。 */
.sider { position: sticky; top: 0; height: 100vh; align-self: flex-start; }
.brand { font-size: 15px; font-weight: 700; padding: 16px 18px 8px; letter-spacing: 0.5px }
.sider-foot { padding: 8px 10px 12px; border-top: 1px solid var(--n-border-color, #eceef1) }
.topbar {
  height: 48px; padding: 0 20px; display: flex; align-items: center; justify-content: space-between;
  border-bottom: 1px solid rgba(128,128,128,0.12); position: sticky; top: 0; z-index: 10;
  backdrop-filter: blur(6px);
}
.topbar .title { font-size: 15px; font-weight: 600 }
.content { padding: 16px 20px 32px; max-width: 1600px; margin: 0 auto }
.dl-bar {
  position: fixed; right: 16px; bottom: 16px; width: 320px; z-index: 1000;
  padding: 10px 12px; border-radius: 8px;
  background: var(--n-card-color, #fff);
  border: 1px solid var(--n-border-color, #eceef1);
  box-shadow: 0 4px 16px rgba(0,0,0,0.14);
}
.dl-head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px }
.dl-title { font-size: 13px; font-weight: 600; white-space: nowrap }
.dl-text { font-size: 11px; color: var(--n-text-color-3, #888); white-space: nowrap; overflow: hidden; text-overflow: ellipsis }
.dl-track { height: 6px; margin-top: 8px; border-radius: 3px; overflow: hidden; background: var(--n-color-hover, #eef0f2) }
.dl-fill { height: 100%; background: #18a058; transition: width 0.3s ease }
</style>
