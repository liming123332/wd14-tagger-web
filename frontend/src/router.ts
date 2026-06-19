import { createRouter, createWebHistory } from 'vue-router'
import UploadPage from './views/UploadPage.vue'
import GalleryPage from './views/GalleryPage.vue'
import DetailPage from './views/DetailPage.vue'
import BatchDetailPage from './views/BatchDetailPage.vue'
import RandomPage from './views/RandomPage.vue'
import PromptBoxPage from './views/PromptBoxPage.vue'
import SettingsPage from './views/SettingsPage.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/gallery' },
    { path: '/upload', component: UploadPage },
    { path: '/gallery', component: GalleryPage },
    { path: '/random', component: RandomPage },
    { path: '/detail/:id', component: DetailPage, props: true },
    { path: '/batch/:id', component: BatchDetailPage, props: true },
    { path: '/promptbox', component: PromptBoxPage },
    { path: '/settings', component: SettingsPage },
  ],
})
