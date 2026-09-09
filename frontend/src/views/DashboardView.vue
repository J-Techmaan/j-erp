<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useApprovalStore } from '../stores/approvals'
import { api, errorMessage } from '../api/client'
import type { Document } from '../types'
import CalendarPanel from '../components/CalendarPanel.vue'
import DocumentTable from '../components/DocumentTable.vue'
const auth = useAuthStore(), approvals = useApprovalStore(), recent = ref<Document[]>([]), error = ref(''), loading = ref(true)
onMounted(async () => { try { await Promise.all([approvals.load(), api.get<Document[]>('/documents', { params: { scope: 'authored', limit: 5 } }).then(r => recent.value = r.data)]) } catch (e) { error.value = errorMessage(e) } finally { loading.value = false } })
</script>
<template><div class="page-heading"><div><p class="eyebrow">{{ new Date().toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' }) }}</p><h1>{{ auth.user?.display_name }}님, 안녕하세요.</h1><p class="muted">오늘의 일정과 기다리고 있는 결재를 확인하세요.</p></div><RouterLink to="/documents/new" class="button primary">＋ 새 결재 작성</RouterLink></div>
  <p v-if="error" role="alert" class="error">{{ error }}</p>
  <div class="dashboard-grid"><CalendarPanel /><section class="panel pending-panel"><div class="panel-toolbar"><h2>결재 대기 <span class="count">{{ approvals.pending.length }}{{ approvals.pending.length === 100 ? '+' : '' }}</span></h2></div><p class="panel-description">지금 내 확인이 필요한 문서</p><p v-if="loading" class="loading" role="status">불러오는 중…</p><div v-else-if="!approvals.pending.length" class="empty-state compact"><span>✓</span><h3>대기 중인 결재가 없습니다.</h3><p>새 요청이 오면 이곳에 표시됩니다.</p></div><RouterLink v-for="doc in approvals.pending.slice(0, 8)" :key="doc.id" class="pending-item" :to="`/documents/${doc.id}`"><strong>{{ doc.title }}</strong><span>{{ doc.author.display_name }} <i>→</i></span><small>{{ new Date(doc.submitted_at!).toLocaleDateString('ko-KR') }}</small></RouterLink><RouterLink class="panel-bottom-link" to="/documents?scope=pending">결재 대기 전체 보기 →</RouterLink></section></div>
  <section class="panel recent-panel"><div class="panel-toolbar"><h2>최근 작성 문서</h2><RouterLink to="/documents?scope=authored" class="text-link">전체 보기 →</RouterLink></div><DocumentTable :documents="recent" empty="아직 작성한 문서가 없습니다." /></section>
</template>
