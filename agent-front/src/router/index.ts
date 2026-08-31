import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/chat',
  },
  {
    // conversationId 可选：无会话时展示欢迎页，选中会话后为 /chat/:conversationId，可深链、刷新保持
    path: '/chat/:conversationId?',
    name: 'chat',
    component: () => import('@/views/ChatView.vue'),
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/chat',
  },
]

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

export default router
