import { h, type FunctionalComponent } from 'vue'

const S = {
  viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
  'stroke-width': 1.8, 'stroke-linecap': 'round', 'stroke-linejoin': 'round',
  width: '1em', height: '1em',
} as Record<string, any>

const I = (makeChildren: () => any[]): FunctionalComponent =>
  (() => h('svg', S, makeChildren())) as any

export const IconUpload = I(() => [
  h('path', { d: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4' }),
  h('polyline', { points: '17 8 12 3 7 8' }),
  h('line', { x1: 12, y1: 3, x2: 12, y2: 15 }),
])
export const IconGallery = I(() => [
  h('rect', { x: 3, y: 3, width: 7, height: 7, rx: 1 }),
  h('rect', { x: 14, y: 3, width: 7, height: 7, rx: 1 }),
  h('rect', { x: 14, y: 14, width: 7, height: 7, rx: 1 }),
  h('rect', { x: 3, y: 14, width: 7, height: 7, rx: 1 }),
])
export const IconRandom = I(() => [
  h('polyline', { points: '16 3 21 3 21 8' }),
  h('line', { x1: 4, y1: 20, x2: 21, y2: 3 }),
  h('polyline', { points: '21 16 21 21 16 21' }),
  h('line', { x1: 15, y1: 15, x2: 21, y2: 21 }),
  h('line', { x1: 4, y1: 4, x2: 9, y2: 9 }),
])
export const IconStar = I(() => [
  h('polygon', { points: '12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2' }),
])
export const IconEdit = I(() => [
  h('path', { d: 'M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7' }),
  h('path', { d: 'M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z' }),
])
export const IconSettings = I(() => [
  h('circle', { cx: 12, cy: 12, r: 3 }),
  h('path', { d: 'M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z' }),
])
export const IconCheck = I(() => [
  h('polyline', { points: '20 6 9 17 4 12' }),
])
export const IconCopy = I(() => [
  h('rect', { x: 9, y: 9, width: 13, height: 13, rx: 2 }),
  h('path', { d: 'M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1' }),
])
export const IconDownload = I(() => [
  h('path', { d: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4' }),
  h('polyline', { points: '7 10 12 15 17 10' }),
  h('line', { x1: 12, y1: 15, x2: 12, y2: 3 }),
])
export const IconTrash = I(() => [
  h('polyline', { points: '3 6 5 6 21 6' }),
  h('path', { d: 'M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2' }),
])
export const IconSearch = I(() => [
  h('circle', { cx: 11, cy: 11, r: 8 }),
  h('line', { x1: 21, y1: 21, x2: 16.65, y2: 16.65 }),
])
export const IconClose = I(() => [
  h('line', { x1: 18, y1: 6, x2: 6, y2: 18 }),
  h('line', { x1: 6, y1: 6, x2: 18, y2: 18 }),
])
export const IconPlus = I(() => [
  h('line', { x1: 12, y1: 5, x2: 12, y2: 19 }),
  h('line', { x1: 5, y1: 12, x2: 19, y2: 12 }),
])
export const IconImage = I(() => [
  h('rect', { x: 3, y: 3, width: 18, height: 18, rx: 2 }),
  h('circle', { cx: 8.5, cy: 8.5, r: 1.5 }),
  h('polyline', { points: '21 15 16 10 5 21' }),
])
export const IconSun = I(() => [
  h('circle', { cx: 12, cy: 12, r: 5 }),
  h('line', { x1: 12, y1: 1, x2: 12, y2: 3 }),
  h('line', { x1: 12, y1: 21, x2: 12, y2: 23 }),
  h('line', { x1: 4.22, y1: 4.22, x2: 5.64, y2: 5.64 }),
  h('line', { x1: 18.36, y1: 18.36, x2: 19.78, y2: 19.78 }),
  h('line', { x1: 1, y1: 12, x2: 3, y2: 12 }),
  h('line', { x1: 21, y1: 12, x2: 23, y2: 12 }),
  h('line', { x1: 4.22, y1: 19.78, x2: 5.64, y2: 18.36 }),
  h('line', { x1: 18.36, y1: 5.64, x2: 19.78, y2: 4.22 }),
])
export const IconMoon = I(() => [
  h('path', { d: 'M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z' }),
])
export const IconMonitor = I(() => [
  h('rect', { x: 2, y: 3, width: 20, height: 14, rx: 2 }),
  h('line', { x1: 8, y1: 21, x2: 16, y2: 21 }),
  h('line', { x1: 12, y1: 17, x2: 12, y2: 21 }),
])
export const IconFolderTag = I(() => [
  // 文件夹轮廓
  h('path', { d: 'M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2z' }),
  // 右下实心小圆点：表示「打标」
  h('circle', { cx: 17.5, cy: 15.5, r: 1.3, fill: 'currentColor', stroke: 'none' }),
])
export const IconCharacter = I(() => [
  h('circle', { cx: 12, cy: 8, r: 4 }),
  h('path', { d: 'M4 21a8 8 0 0 1 16 0' }),
])
export const IconArtist = I(() => [
  // 调色板
  h('path', { d: 'M12 2a10 10 0 1 0 0 20 2 2 0 0 0 2-2 2 2 0 0 1 2-2h2a6 6 0 0 0 6-6 10 10 0 0 0-12-10z' }),
  h('circle', { cx: 7.5, cy: 10.5, r: 1.2, fill: 'currentColor', stroke: 'none' }),
  h('circle', { cx: 12, cy: 7.5, r: 1.2, fill: 'currentColor', stroke: 'none' }),
  h('circle', { cx: 16.5, cy: 10.5, r: 1.2, fill: 'currentColor', stroke: 'none' }),
])
