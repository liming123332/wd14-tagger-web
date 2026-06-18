import { createRouter, createWebHistory } from 'vue-router'
import UploadPage from './views/UploadPage.vue'
import GalleryPage from './views/GalleryPage.vue'
import DetailPage from './views/DetailPage.vue'
import SettingsPage from './views/SettingsPage.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/gallery' },
    { path: '/upload', component: UploadPage },
    { path: '/gallery', component: GalleryPage },
    { path: '/detail/:id', component: DetailPage, props: true },
    { path: '/settings', component: SettingsPage },
  ],
})
