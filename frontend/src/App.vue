<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { errorMessage } from './api/client'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'
import { useDocumentStore } from './stores/documents'
import { useApprovalStore } from './stores/approvals'
import { useScheduleStore } from './stores/schedules'
import { useGroupStore } from './stores/groups'
const route = useRoute(), router = useRouter(), auth = useAuthStore()
const documents = useDocumentStore(), approvals = useApprovalStore(), schedules = useScheduleStore()
const groups = useGroupStore()
const logoutBusy = ref(false), logoutError = ref('')
function clearWorkspace() { documents.clear(); approvals.clear(); schedules.clear() }
function expired() {
  auth.clear(); clearWorkspace()
  if (!['/login', '/signup'].includes(route.path) && !route.path.startsWith('/invite/')) void router.replace({ path: '/login', query: { redirect: route.fullPath } })
}
async function logout() {
  logoutBusy.value = true; logoutError.value = ''
  try { await auth.logout(); clearWorkspace(); groups.clear(); await router.replace('/login') }
  catch (e) { logoutError.value = errorMessage(e) }
  finally { logoutBusy.value = false }
}
function refreshSession() { if (auth.user) void auth.restore(true).then(() => { if (!auth.user) expired() }) }
watch(() => auth.user?.id, clearWorkspace)
onMounted(() => {
  window.addEventListener('jerp-unauthorized', expired)
  window.addEventListener('focus', refreshSession)
})
onUnmounted(() => {
  window.removeEventListener('jerp-unauthorized', expired)
  window.removeEventListener('focus', refreshSession)
})
</script>

<template>
  <RouterView v-if="['/login', '/signup'].includes(route.path) || route.path.startsWith('/invite/')" :key="route.fullPath" />
  <div v-else-if="auth.user" class="app-shell">
    <header class="app-header">
      <RouterLink to="/" class="brand"><span class="brand-mark">J</span> J-ERP <span class="brand-caption">WORKSPACE</span></RouterLink>
      <div class="header-user"><span class="avatar">{{ auth.user.display_name.slice(0, 1) }}</span><span>{{ auth.user.display_name }}<small>{{ auth.user.email }}</small></span><button class="quiet" :disabled="logoutBusy" @click="logout">로그아웃</button></div>
    </header>
    <aside class="sidebar">
      <p class="nav-caption">내 업무 공간</p>
      <label v-if="groups.groups.length" class="group-switcher">현재 그룹<select :value="groups.currentId" @change="groups.select(Number(($event.target as HTMLSelectElement).value)); router.push('/')"><option v-for="group in groups.groups" :key="group.id" :value="group.id">{{ group.name }}</option></select></label>
      <RouterLink to="/" :class="{ active: route.path === '/' }"><span>▦</span> 대시보드</RouterLink>
      <RouterLink to="/documents/new" :class="{ active: route.path === '/documents/new' }"><span>＋</span> 새 결재 작성</RouterLink>
      <p class="nav-caption">전자결재</p>
      <RouterLink to="/documents?scope=inbox" :class="{ active: route.query.scope === 'inbox' }"><span>◷</span> 결재함</RouterLink>
      <RouterLink to="/documents?scope=authored" :class="{ active: route.query.scope === 'authored' }"><span>▤</span> 상신함</RouterLink>
      <RouterLink to="/documents?scope=group" :class="{ active: ['group', 'notified'].includes(String(route.query.scope)) }"><span>♧</span> 그룹 문서함</RouterLink>
      <p class="nav-caption">프로젝트</p>
      <RouterLink to="/projects" :class="{ active: route.path.startsWith('/projects') }"><span>▦</span> 프로젝트 관리</RouterLink>
      <p class="nav-caption">일정 관리</p>
      <RouterLink to="/calendar" :class="{ active: route.path === '/calendar' }"><span>□</span> 그룹 일정</RouterLink>
      <RouterLink to="/groups/settings" :class="{ active: route.path === '/groups/settings' }"><span>⚙</span> 그룹 관리</RouterLink>
      <div class="sidebar-note"><span class="status-dot"></span> 내 업무 공간<br /><small>전자결재 · 개인 일정</small></div>
    </aside>
    <main class="main"><p v-if="logoutError" class="error" role="alert">{{ logoutError }}</p><RouterView :key="(route.path.startsWith('/projects') ? route.path : route.fullPath) + auth.user.id" /></main>
  </div>
</template>
