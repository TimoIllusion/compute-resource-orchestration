import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from '../views/DashboardView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: DashboardView
    },
    {
      path: '/reservations',
      name: 'reservations',
      // Lazy load component for better performance
      component: () => import('../views/ReservationsView.vue')
    }
  ]
})

export default router