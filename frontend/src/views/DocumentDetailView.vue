<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, errorMessage } from '../api/client'
import { useDocumentStore } from '../stores/documents'
import { useAuthStore } from '../stores/auth'
import { formatDate, stepLabels, typeLabels, type Attachment } from '../types'
import StatusBadge from '../components/StatusBadge.vue'
const route = useRoute(), router = useRouter(), store = useDocumentStore(), auth = useAuthStore()
const loading = ref(true), busy = ref(false), error = ref(''), comment = ref(''), message = ref('')
const doc = computed(() => store.selected)
const canAct = computed(() => doc.value?.status === 'IN_PROGRESS' && doc.value.steps.some(s => s.user_id === auth.user?.id && s.status === 'CURRENT' && s.approval_type !== 'NOTIFICATION'))
const canEdit = computed(() => doc.value?.status === 'DRAFT' && doc.value.author_id === auth.user?.id)
const canCancel = computed(() => doc.value?.status === 'IN_PROGRESS' && doc.value.author_id === auth.user?.id)
const canRecreate = computed(() => ['REJECTED', 'CANCELLED'].includes(doc.value?.status || '') && doc.value?.author_id === auth.user?.id)
const actionLabels: Record<string, string> = { SUBMITTED: '상신', APPROVED: '승인', REJECTED: '반려', CANCELLED: '상신취소', NOTIFIED: '통보 완료' }
async function load() { loading.value = true; error.value = ''; store.selected = null; try { await store.get(Number(route.params.id)) } catch (e) { error.value = errorMessage(e) } finally { loading.value = false } }
async function action(name: 'submit' | 'approve' | 'reject') {
  if (!doc.value) return
  if (name === 'reject' && !comment.value.trim()) { error.value = '반려 사유를 입력하세요.'; return }
  busy.value = true; error.value = ''; message.value = ''
  try { await store.action(doc.value.id, name, doc.value.revision, comment.value); comment.value = ''; message.value = name === 'reject' ? '문서를 반려했습니다.' : name === 'submit' ? '문서를 상신했습니다.' : '승인했습니다.' } catch (e) { error.value = errorMessage(e) } finally { busy.value = false }
}
async function recreate() { if (!doc.value) return; busy.value = true; error.value = ''; try { const copy = await store.recreate(doc.value.id); await router.push(`/documents/${copy.id}/edit`) } catch (e) { error.value = errorMessage(e) } finally { busy.value = false } }
async function cancel() { if (!doc.value || !window.confirm('상신을 취소하시겠습니까?')) return; busy.value = true; error.value = ''; try { await store.action(doc.value.id, 'cancel', doc.value.revision); message.value = '상신을 취소했습니다.' } catch (e) { error.value = errorMessage(e) } finally { busy.value = false } }
async function download(file: Attachment) {
  try { const { data } = await api.get(`/attachments/${file.id}/download`, { responseType: 'blob' }); const url = URL.createObjectURL(data); const link = document.createElement('a'); link.href = url; link.download = file.original_filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000) } catch (e) { error.value = errorMessage(e) }
}
onMounted(load)
</script>
<template><p v-if="loading" class="loading" role="status">문서를 불러오는 중입니다…</p><p v-if="error" class="error" role="alert">{{ error }} <button :disabled="busy" @click="load">새로고침</button></p><p v-if="message" class="success" role="status">{{ message }}</p>
  <template v-if="!loading && doc"><div class="page-heading"><div><p class="eyebrow">{{ doc.document_number }}</p><h1>{{ doc.title }}</h1><p class="muted">{{ doc.author.display_name }} 작성 · {{ formatDate(doc.created_at) }}</p></div><StatusBadge :status="doc.status" /></div>
  <div class="detail-grid"><div><section class="panel form-panel"><div class="document-metadata"><span>상신일 <strong>{{ formatDate(doc.submitted_at) }}</strong></span><span v-if="doc.status === 'REJECTED'">반려일 <strong>{{ formatDate(doc.rejected_at) }}</strong></span><span v-else>완결일 <strong>{{ formatDate(doc.completed_at) }}</strong></span></div><h2>문서 내용</h2><div class="document-content">{{ doc.content || '내용이 없습니다.' }}</div><div class="attachment-section"><h3>첨부파일 <span class="muted">{{ doc.attachments.length }}</span></h3><p v-if="!doc.attachments.length" class="muted">첨부파일이 없습니다.</p><button v-for="file in doc.attachments" :key="file.id" class="download-file" @click="download(file)">▧ {{ file.original_filename }} <small>{{ Math.ceil(file.file_size / 1024) }} KB</small><span>↓ 다운로드</span></button></div></section>
  <section v-if="doc.history.length" class="panel form-panel history-panel"><h2>처리 이력</h2><ol class="history-list"><li v-for="entry in doc.history" :key="entry.id"><span class="history-dot"></span><div><strong>{{ entry.user.display_name }} · {{ actionLabels[entry.action] || entry.action }}</strong><small>{{ entry.round_number }}차 상신 · {{ formatDate(entry.acted_at) }}</small><p v-if="entry.comment">{{ entry.comment }}</p></div></li></ol></section></div>
  <section class="panel form-panel approval-detail"><h2>결재 진행</h2><p class="muted">{{ doc.round_number }}차 상신</p><ol class="step-timeline"><li v-for="step in doc.steps" :key="step.id" :class="step.status"><span class="timeline-marker">{{ step.status === 'APPROVED' || step.status === 'NOTIFIED' ? '✓' : step.step_order }}</span><div><div class="step-heading"><strong>{{ step.user.display_name }}</strong><span>{{ typeLabels[step.approval_type] }}</span></div><p class="step-status">{{ stepLabels[step.status] }}</p><small v-if="step.acted_at">{{ formatDate(step.acted_at) }}</small><p v-if="step.comment" class="step-comment">{{ step.comment }}</p></div></li></ol>
    <div v-if="canAct" class="action-box"><label>결재 의견 / 반려 사유<textarea v-model="comment" rows="3" maxlength="2000" placeholder="반려 시 사유를 입력하세요." :disabled="busy"></textarea></label><div class="button-row"><button class="danger" :disabled="busy" @click="action('reject')">반려</button><button class="primary" :disabled="busy" @click="action('approve')">승인</button></div></div>
    <div v-if="canCancel" class="action-box"><button class="danger" :disabled="busy" @click="cancel">상신취소</button></div><div v-else-if="canEdit" class="action-box"><RouterLink :to="`/documents/${doc.id}/edit`" class="button primary">문서 수정 및 상신</RouterLink></div><div v-else-if="canRecreate" class="action-box"><p>원본은 그대로 보관됩니다. 새 기안 문서로 내용을 복사합니다.</p><button class="primary" :disabled="busy" @click="recreate">재작성</button></div><p v-else-if="doc.status === 'COMPLETED'" class="helper-box">모든 결재가 완료되었습니다. 통보 대상에게도 완결 상태가 표시됩니다.</p><p v-else-if="doc.status === 'REJECTED'" class="helper-box">이 문서는 반려되어 종료되었습니다.</p><p v-else-if="doc.status === 'CANCELLED'" class="helper-box">이 문서는 상신이 취소되어 종료되었습니다.</p>
  </section></div></template>
</template>
