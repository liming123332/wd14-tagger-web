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
import {
  IconUpload, IconGallery, IconRandom, IconStar, IconEdit, IconSettings,
  IconSun, IconMoon, IconMonitor,
} from './components/icons'

const router = useRouter()
const route = useRoute()
const { mode, effective, setMode } = useTheme()

const theme = computed<GlobalTheme | null>(() => (effective.value === 'dark' ? darkTheme : null))
const overrides = computed(() => (effective.value === 'dark' ? darkOverrides : lightOverrides))

const ITEMS = [
  { label: '上传', key: '/upload', icon: IconUpload },
  { label: '图库', key: '/gallery', icon: IconGallery },
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
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<style scoped>
.brand { font-size: 15px; font-weight: 700; padding: 16px 18px 8px; letter-spacing: 0.5px }
.sider-foot { padding: 8px 10px 12px; border-top: 1px solid var(--n-border-color, #eceef1) }
.topbar {
  height: 48px; padding: 0 20px; display: flex; align-items: center; justify-content: space-between;
  border-bottom: 1px solid rgba(128,128,128,0.12); position: sticky; top: 0; z-index: 10;
  backdrop-filter: blur(6px);
}
.topbar .title { font-size: 15px; font-weight: 600 }
.content { padding: 16px 20px 32px; max-width: 1600px; margin: 0 auto }
</style>
