import { createRouter, createWebHistory } from 'vue-router'
import UploadPage from './views/UploadPage.vue'
import PathTagPage from './views/PathTagPage.vue'
import GalleryPage from './views/GalleryPage.vue'
import DetailPage from './views/DetailPage.vue'
import BatchDetailPage from './views/BatchDetailPage.vue'
import RandomPage from './views/RandomPage.vue'
import CollectionListPage from './views/CollectionListPage.vue'
import PromptboxDetailPage from './views/PromptboxDetailPage.vue'
import PromptBoxPage from './views/PromptBoxPage.vue'
import SettingsPage from './views/SettingsPage.vue'
import CharactersPage from './views/CharactersPage.vue'
import CharacterDetailPage from './views/CharacterDetailPage.vue'
import ArtistsPage from './views/ArtistsPage.vue'
import ArtistDetailPage from './views/ArtistDetailPage.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/gallery' },
    { path: '/upload', component: UploadPage },
    { path: '/pathtag', component: PathTagPage },
    { path: '/gallery', component: GalleryPage },
    { path: '/characters', component: CharactersPage },
    { path: '/characters/:source/:key', component: CharacterDetailPage, props: true },
    { path: '/artists', component: ArtistsPage },
    { path: '/artists/:source/:key', component: ArtistDetailPage, props: true },
    { path: '/random', component: RandomPage },
    { path: '/detail/:id', component: DetailPage, props: true },
    { path: '/batch/:id', component: BatchDetailPage, props: true },
    { path: '/collections', component: CollectionListPage },
    { path: '/collections/:id', component: PromptboxDetailPage, props: true },
    { path: '/promptbox', component: PromptBoxPage },
    { path: '/settings', component: SettingsPage },
  ],
})
