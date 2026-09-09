<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { api, errorMessage } from '../api/client'
import { useDocumentStore } from '../stores/documents'
import { useAuthStore } from '../stores/auth'
import { useGroupStore } from '../stores/groups'
import { typeLabels, type ApprovalType, type Attachment, type User } from '../types'

interface LineEntry { user: User; approval_type: ApprovalType }
const route = useRoute(), router = useRouter(), store = useDocumentStore(), auth = useAuthStore()
const groups = useGroupStore()
const id = ref<number | undefined>(route.params.id ? Number(route.params.id) : undefined), revision = ref<number>()
const title = ref(''), content = ref(''), line = ref<LineEntry[]>([]), search = ref(''), results = ref<User[]>([]), files = ref<File[]>([]), attachments = ref<Attachment[]>([])
const busy = ref(false), loading = ref(false), error = ref(''), searchError = ref(''), notice = ref(''), dirty = ref(false), fileInput = ref<HTMLInputElement | null>(null)
const submitModal = ref(false), submissionMessage = ref('')
const canSubmit = computed(() => line.value.some(s => s.approval_type !== 'NOTIFICATION'))
let searchSequence = 0
async function searchUsers() {
  const sequence = ++searchSequence
  searchError.value = ''
  try { const { data } = await api.get<User[]>('/users/search', { params: { q: search.value, group_id: groups.currentId } }); if (sequence === searchSequence) results.value = data } catch (e) { if (sequence === searchSequence) searchError.value = errorMessage(e) }
}
function add(user: User) { if (!line.value.some(s => s.user.id === user.id)) { line.value.push({ user, approval_type: 'APPROVAL' }); dirty.value = true } }
function move(index: number, delta: number) { const target = index + delta; if (target < 0 || target >= line.value.length) return; [line.value[index], line.value[target]] = [line.value[target], line.value[index]]; dirty.value = true }
function chooseFiles(event: Event) { files.value.push(...Array.from((event.target as HTMLInputElement).files || [])); dirty.value = true; (event.target as HTMLInputElement).value = '' }
async function save(submit: boolean) {
  busy.value = true; error.value = ''; notice.value = ''
  try {
    let doc = await store.save({ title: title.value, content: content.value, steps: line.value.map(s => ({ user_id: s.user.id, approval_type: s.approval_type })), ...(id.value ? { revision: revision.value } : {}) }, id.value)
    id.value = doc.id; revision.value = doc.revision
    // Remove each successful upload immediately so retrying never duplicates it.
    while (files.value.length) {
      const data = new FormData(); data.append('file', files.value[0]); data.append('revision', String(revision.value))
      const uploaded = await api.post<Attachment>(`/documents/${doc.id}/attachments`, data)
      attachments.value.push(uploaded.data); files.value.shift()
      doc = await store.get(doc.id); revision.value = doc.revision
    }
    dirty.value = false
    if (submit) { submitModal.value = true }
    else { notice.value = '임시저장했습니다.'; await router.replace(`/documents/${doc.id}/edit`) }
  } catch (e) { error.value = errorMessage(e) } finally { busy.value = false }
}
async function confirmSubmit() {
  if (!id.value || !revision.value || !window.confirm('상신하시겠습니까?')) return
  busy.value = true; error.value = ''
  try { const doc = await store.action(id.value, 'submit', revision.value, submissionMessage.value); submitModal.value = false; await router.push(`/documents/${doc.id}`) }
  catch (e) { error.value = errorMessage(e) } finally { busy.value = false }
}
onBeforeRouteLeave(() => { if (auth.user && dirty.value && !busy.value && !window.confirm('저장하지 않은 변경사항이 있습니다. 이동할까요?')) return false })
onMounted(async () => {
  loading.value = true
  try {
    if (id.value) {
      const doc = await store.get(id.value)
      if (doc.status !== 'DRAFT' || doc.author_id !== auth.user?.id) { await router.replace(`/documents/${doc.id}`); return }
      title.value = doc.title; content.value = doc.content; line.value = doc.steps.map(s => ({ user: s.user, approval_type: s.approval_type })); revision.value = doc.revision; attachments.value = doc.attachments
    }
    await searchUsers()
  } catch (e) { error.value = errorMessage(e) } finally { loading.value = false }
})
</script>
<template><div class="page-heading"><div><p class="eyebrow">NEW APPROVAL</p><h1>{{ id ? '기안 문서 수정' : '새 결재 작성' }}</h1><p class="muted">내용을 작성하고 함께 확인할 결재자를 지정하세요.</p></div><RouterLink to="/documents?scope=authored" class="text-link">작성 문서로 돌아가기 →</RouterLink></div>
  <p v-if="error" class="error" role="alert">{{ error }}</p><p v-if="notice" class="success" role="status">{{ notice }}</p><p v-if="loading" role="status">문서를 불러오는 중입니다…</p>
  <form v-else @submit.prevent="save(true)"><fieldset :disabled="busy"><div class="document-compose"><section class="panel form-panel"><h2><span class="section-index">01</span> 문서 내용</h2><label>제목 <span class="required">*</span><input v-model="title" required maxlength="200" placeholder="예: 사무용 장비 구매 요청" @input="dirty = true" /></label><label>내용<textarea v-model="content" rows="13" maxlength="100000" placeholder="결재를 요청할 내용을 입력하세요." @input="dirty = true"></textarea></label><div class="attachment-section"><h3>첨부파일</h3><label class="upload-zone">＋ 파일 선택<input ref="fileInput" type="file" multiple @change="chooseFiles" /><small>기본 10 MB / TXT, PDF, 이미지, CSV, XLSX, DOCX</small></label><ul class="file-list"><li v-for="file in attachments" :key="file.id">▧ {{ file.original_filename }} <small>저장됨</small></li><li v-for="(file, index) in files" :key="index">▧ {{ file.name }} <small>{{ Math.ceil(file.size / 1024) }} KB</small><button type="button" class="quiet" :aria-label="`${file.name} 선택 취소`" @click="files.splice(index, 1)">✕</button></li></ul></div></section>
  <section class="panel form-panel approval-editor approval-bar"><h2><span class="section-index">02</span> 결재선 설정</h2><label>사용자 검색<input v-model="search" placeholder="이름 또는 사용자명 검색" @input="searchUsers" /></label><p v-if="searchError" role="alert" class="error">{{ searchError }}</p><div class="search-results"><button v-for="user in results" :key="user.id" type="button" :disabled="line.some(s => s.user.id === user.id)" @click="add(user)"><span class="avatar small">{{ user.display_name[0] }}</span><span>{{ user.display_name }}</span><small>{{ line.some(s => s.user.id === user.id) ? '추가됨' : '＋ 추가' }}</small></button><p v-if="!results.length" class="muted">검색 결과가 없습니다.</p></div>
    <div class="line-heading"><h3>선택된 결재선</h3><span class="muted">{{ line.length }}명</span></div><p v-if="!line.length" class="muted">위에서 결재자를 선택하세요.</p><ol class="approval-line"><li v-for="(entry, index) in line" :key="entry.user.id"><div class="type-segment" role="radiogroup" :aria-label="`${entry.user.display_name} 결재 유형`"><button v-for="(label, type) in typeLabels" :key="type" type="button" role="radio" :aria-checked="entry.approval_type === type" :class="{ active: entry.approval_type === type }" @click="entry.approval_type = type; dirty = true">{{ label }}</button></div><div class="line-person"><span class="order-number">{{ index + 1 }}</span><strong>{{ entry.user.display_name }}</strong></div><div class="line-controls"><button type="button" :disabled="index === 0" :aria-label="`${entry.user.display_name} 위로`" @click="move(index, -1)">↑</button><button type="button" :disabled="index === line.length - 1" :aria-label="`${entry.user.display_name} 아래로`" @click="move(index, 1)">↓</button><button type="button" :aria-label="`${entry.user.display_name} 삭제`" @click="line.splice(index, 1); dirty = true">삭제</button></div></li></ol><p class="helper-box">결재와 합의는 위에서부터 순서대로 진행됩니다. 통보 대상에게는 완결 또는 반려 결과가 전달됩니다.</p>
  </section></div><div class="editor-footer"><span class="muted">{{ canSubmit ? '결재선을 확인한 후 상신하세요.' : '상신하려면 결재 또는 합의 대상이 필요합니다.' }}</span><div class="button-row"><button type="button" @click="save(false)">{{ busy ? '저장 중…' : '임시저장' }}</button><button type="submit" class="primary" :disabled="!canSubmit || busy">상신</button></div></div></fieldset></form>
  <div v-if="submitModal" class="modal-backdrop" @click.self="submitModal = false"><section class="panel modal-card" role="dialog" aria-modal="true" aria-labelledby="submit-title"><h2 id="submit-title">문서 상신</h2><label>상신 메시지 <span class="muted">선택</span><textarea v-model="submissionMessage" rows="4" maxlength="2000" placeholder="결재자에게 전달할 메시지를 입력하세요."></textarea></label><div class="button-row"><button type="button" :disabled="busy" @click="submitModal = false">취소</button><button type="button" class="primary" :disabled="busy" @click="confirmSubmit">{{ busy ? '상신 중…' : '상신' }}</button></div></section></div>
</template>
