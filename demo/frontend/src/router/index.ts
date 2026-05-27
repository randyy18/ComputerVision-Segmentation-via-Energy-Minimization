import { createRouter, createWebHistory } from 'vue-router'
import UploadView from '@/views/UploadView.vue'
import GameView from '@/views/GameView.vue'
import ProcessingView from '@/views/ProcessingView.vue'
import ResultsView from '@/views/ResultsView.vue'
import LeaderboardView from '@/views/LeaderboardView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'upload', component: UploadView },
    { path: '/game', name: 'game', component: GameView },
    { path: '/processing', name: 'processing', component: ProcessingView },
    { path: '/results', name: 'results', component: ResultsView },
    { path: '/leaderboard', name: 'leaderboard', component: LeaderboardView },
  ],
})

export default router
