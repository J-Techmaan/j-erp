<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, errorMessage } from '../api/client'
import type { Document } from '../types'
import DocumentTable from '../components/DocumentTable.vue'
const route = useRoute(), router = useRouter()
const scope = computed(() => route.query.scope === 'notified' ? 'group' : ['inbox', 'authored', 'group'].includes(String(route.query.scope)) ? String(route.query.scope) : 'authored')
const titles: Record<string, string> = { inbox: '결재함', authored: '상신함', group: '그룹 문서함' }
const status = ref(''), items = ref<Document[]>([]), pending = ref<Document[]>([]), history = ref<Document[]>([])
const page = ref(0), busy = ref(true), error = ref('')
async function load(reset = false) {
  if (reset) page.value = 0
  busy.value = true; error.value = ''
  try {
    if (scope.value === 'inbox') {
      const [waiting, completed] = await Promise.all([api.get<Document[]>('/documents', { params: { scope: 'pending', limit: 100 } }), api.get<Document[]>('/documents', { params: { scope: 'history', limit: 100 } })])
      pending.value = waiting.data; history.value = completed.data
    } else items.value = (await api.get<Document[]>('/documents', { params: { scope: scope.value, status: status.value || undefined, offset: page.value * 20, limit: 20 } })).data
  } catch (e) { error.value = errorMessage(e) } finally { busy.value = false }
}
async function next(delta: number) { page.value += delta; await load() }
async function cancel(doc: Document) { if (!window.confirm('상신을 취소하시겠습니까?')) return; try { await api.post(`/documents/${doc.id}/cancel`, { revision: doc.revision }); await load() } catch (e) { error.value = errorMessage(e) } }
async function recreate(doc: Document) { try { const copy = (await api.post<Document>(`/documents/${doc.id}/recreate`)).data; await router.push(`/documents/${copy.id}/edit`) } catch (e) { error.value = errorMessage(e) } }
onMounted(() => load())
</script>
<template><div class="page-heading"><div><p class="eyebrow">APPROVALS</p><h1>{{ titles[scope] }}</h1><p class="muted">문서의 진행 상태와 처리 내용을 확인하세요.</p></div><RouterLink class="button primary" to="/documents/new">＋ 새 결재 작성</RouterLink></div>
  <p v-if="error" class="error" role="alert">{{ error }} <button @click="load()">다시 시도</button></p><p v-else-if="busy" class="loading" role="status">문서를 불러오는 중입니다…</p>
  <template v-else-if="scope === 'inbox'"><section class="panel inbox-section"><header><h2>결재 대기 <span>{{ pending.length }}</span></h2></header><DocumentTable :documents="pending" empty="처리할 결재가 없습니다." /></section><section class="panel inbox-section"><header><h2>결재 완료 <span>{{ history.length }}</span></h2></header><DocumentTable :documents="history" empty="처리한 결재가 없습니다." /></section></template>
  <section v-else class="panel"><div class="panel-toolbar"><h2>문서 목록</h2><label class="inline-label">상태 <select v-model="status" :disabled="busy" @change="load(true)"><option value="">전체 상태</option><option value="DRAFT">기안</option><option value="IN_PROGRESS">상신중</option><option value="COMPLETED">완결</option><option value="REJECTED">반려</option><option value="CANCELLED">취소됨</option></select></label></div><DocumentTable :documents="items" :actions="scope === 'authored'" @cancel="cancel" @recreate="recreate" /><div class="pagination"><button :disabled="page === 0 || busy" @click="next(-1)">이전</button><span>{{ page + 1 }} 페이지</span><button :disabled="items.length < 20 || busy" @click="next(1)">다음</button></div></section>
</template>
