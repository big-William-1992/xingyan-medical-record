import { createRouter, createWebHashHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import Review from '../views/Review.vue'
import ReportDetail from '../views/ReportDetail.vue'

const routes = [
  { path: '/',         component: Dashboard },
  { path: '/review',   component: Review },
  { path: '/report',   component: ReportDetail },
  { path: '/stats',    component: Dashboard },  // placeholder
  { path: '/settings', component: Dashboard },  // placeholder
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router
