import { createRouter, createWebHistory } from 'vue-router'

import AppShell from '@/components/layout/AppShell.vue'
import { useAuthStore } from '@/stores/auth'
import LandingView from '@/views/LandingView.vue'
import LoginView from '@/views/LoginView.vue'
import PortfolioDetailView from '@/views/PortfolioDetailView.vue'
import PortfolioListView from '@/views/PortfolioListView.vue'
import RegisterView from '@/views/RegisterView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'landing',
      component: LandingView,
      meta: { guestOnly: true },
    },
    {
      // Mount path is /portfolios, not / -- frees up / for the public landing page above.
      // Existing URLs are unchanged: children are relative to this, so /portfolios and
      // /portfolios/:id resolve exactly as they did when this route's own path was /.
      path: '/portfolios',
      component: AppShell,
      meta: { requiresAuth: true },
      children: [
        { path: '', name: 'portfolios', component: PortfolioListView },
        { path: ':portfolioId', name: 'portfolio-detail', component: PortfolioDetailView },
      ],
    },
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { guestOnly: true },
    },
    {
      path: '/register',
      name: 'register',
      component: RegisterView,
      meta: { guestOnly: true },
    },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  const requiresAuth = to.matched.some((record) => record.meta.requiresAuth)
  const guestOnly = to.matched.some((record) => record.meta.guestOnly)

  if (requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (guestOnly && auth.isAuthenticated) {
    return { name: 'portfolios' }
  }
})

export default router
