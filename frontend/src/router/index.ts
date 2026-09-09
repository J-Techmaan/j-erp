import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import LoginView from '../views/LoginView.vue'
import InviteView from '../views/InviteView.vue'
import DashboardView from '../views/DashboardView.vue'
import DocumentsView from '../views/DocumentsView.vue'
import DocumentEditView from '../views/DocumentEditView.vue'
import DocumentDetailView from '../views/DocumentDetailView.vue'
import CalendarView from '../views/CalendarView.vue'
import GroupStartView from '../views/GroupStartView.vue'
import GroupSettingsView from '../views/GroupSettingsView.vue'
import ProjectControlView from '../views/ProjectControlView.vue'
import { useGroupStore } from '../stores/groups'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/invite/:token', component: InviteView },
    { path: '/login', component: LoginView },
    { path: '/signup', component: LoginView },
    { path: '/groups/start', component: GroupStartView },
    { path: '/groups/settings', component: GroupSettingsView },
    { path: '/', component: DashboardView },
    { path: '/projects', component: ProjectControlView },
    { path: '/projects/:projectId', component: ProjectControlView },
    { path: '/documents', component: DocumentsView },
    { path: '/documents/new', component: DocumentEditView },
    { path: '/documents/:id/edit', component: DocumentEditView },
    { path: '/documents/:id', component: DocumentDetailView },
    { path: '/calendar', component: CalendarView },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})
router.beforeEach(async to => {
  const auth = useAuthStore()
  await auth.restore()
  if (to.path.startsWith('/invite/')) return
  const publicPage = ['/login', '/signup'].includes(to.path)
  if (!auth.user && !publicPage) return { path: '/login', query: { redirect: to.fullPath } }
  if (auth.user && publicPage) return '/'
  if (auth.user) {
    const groups = useGroupStore()
    await groups.load()
    if (!groups.groups.length && to.path !== '/groups/start') return '/groups/start'
    if (groups.groups.length && to.path === '/groups/start') return '/'
  }
})
export default router
