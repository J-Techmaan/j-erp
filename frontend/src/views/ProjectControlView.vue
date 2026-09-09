<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { api, errorMessage } from '../api/client'
import { formatDate, type Document } from '../types'
import { projectTabs, projectLabel, rowTitle, fieldSpec, type ProjectRow, type ProjectMeta, type ProjectDashboard, type Activity, type FieldValue, type Option } from '../types/projects'
import ProjectOverview from '../components/ProjectOverview.vue'
import ProjectRecordForm from '../components/ProjectRecordForm.vue'

const route = useRoute(), router = useRouter()
const projectId = Number(route.params.projectId) || null
const sections: Record<string, { label: string; tabs: Record<string, string> }> = {
  overview: { label: '개요', tabs: { dashboard: '전체 현황', readiness: '오픈 준비도', activity: '활동 이력' } },
  work: { label: '업무', tabs: { tasks: '업무·액션' } },
  plan: { label: '계획', tabs: { timeline: '타임라인', wbs: 'WBS', milestones: '마일스톤', dependencies: '의존성' } },
  control: { label: '통제', tabs: { risks: '위험', issues: '이슈', ecr: '변경', decisions: '의사결정' } },
  resources: { label: '자원', tabs: { budget: '예산', vendors: '업체', documents: '문서' } },
}
const validTabs = Object.values(sections).flatMap(s => Object.keys(s.tabs)).concat('eco')
const tab = ref(projectId ? (validTabs.includes(String(route.query.view)) ? String(route.query.view) : 'dashboard') : 'projects')
const section = computed(() => Object.keys(sections).find(k => Object.hasOwn(sections[k]!.tabs, tab.value === 'eco' ? 'ecr' : tab.value)) || 'overview')
const workBucket = ref('ALL')
watch(() => route.query.view, value => { if (projectId && validTabs.includes(String(value)) && tab.value !== value) { tab.value = String(value); selected.value = null; formKind.value = ''; page.value = 0; search.value = ''; statusFilter.value = '' } })
const projects = ref<ProjectRow[]>([]), project = ref<ProjectRow | null>(null)
const records = ref<Record<string, ProjectRow[]>>({}), meta = ref<ProjectMeta | null>(null)
const dashboard = ref<ProjectDashboard | null>(null), activity = ref<Activity[]>([]), documents = ref<Document[]>([])
const busy = ref(false), loading = ref(true), error = ref(''), message = ref(''), search = ref(''), statusFilter = ref('')
const selected = ref<ProjectRow | null>(null), formKind = ref(''), editId = ref<number | null>(null), editRevision = ref<number | null>(null)
const form = ref<Record<string, FieldValue>>({}), comment = ref(''), page = ref(0), activityPage = ref(0)
const manager = computed(() => Boolean(project.value?.can_manage))
const schema = computed(() => meta.value?.schemas[formKind.value])
const rows = computed(() => tab.value === 'projects' ? projects.value : (tab.value === 'tasks' && workBucket.value !== 'ALL' ? dashboard.value?.buckets[workBucket.value] || [] : records.value[tab.value] || []))
const filtered = computed(() => rows.value.filter(row => (!search.value || rowTitle(row).toLowerCase().includes(search.value.toLowerCase())) && (!statusFilter.value || (row.status || row.implementation_status) === statusFilter.value)))
const statuses = computed(() => [...new Set(rows.value.map(row => String(row.status || row.implementation_status || '')).filter(Boolean))])
const visible = computed(() => filtered.value.slice(page.value * 20, page.value * 20 + 20))
const selectedActivity = computed(() => activity.value.filter(a => a.entity_type === tab.value && a.entity_id === selected.value?.id))
const taskComments = computed(() => (records.value.comments || []).filter(c => c.task_id === selected.value?.id))
const taskDependencies = computed(() => (records.value.dependencies || []).filter(d => d.successor_task_id === selected.value?.id))
const related = computed(() => {
  if (tab.value !== 'tasks' || !selected.value) return []
  const id = selected.value.id
  return ['ecr', 'eco', 'issues', 'risks', 'decisions'].flatMap(kind => (records.value[kind] || []).filter(r => r.linked_task === id || (Array.isArray(r.affected_tasks) && r.affected_tasks.includes(id)) || (Array.isArray(r.related_tasks) && r.related_tasks.includes(id))).map(row => ({ kind, row })))
})
const wbsTree = computed(() => {
  const output: { row: ProjectRow; depth: number }[] = [], visited = new Set<number>()
  function walk(parent: number | null, depth: number) {
    for (const row of records.value.wbs || []) if (row.parent_id === parent && !visited.has(row.id)) { visited.add(row.id); output.push({ row, depth }); walk(row.id, depth + 1) }
  }
  walk(null, 0)
  return output
})
const options = computed<Record<string, Option[]>>(() => {
  const choices = (kind: string) => (records.value[kind] || []).map(row => ({ id: row.id, name: `${row.task_code || row.wbs_code || row.ecr_no || ''} ${rowTitle(row)}` }))
  const tasks = choices('tasks'), docs = documents.value.map(d => ({ id: d.id, name: `${d.document_number} ${d.title}` }))
  return { owner: meta.value?.members || [], project_manager: meta.value?.members || [], reviewer: meta.value?.members || [],
    wbs_id: choices('wbs'), parent_id: choices('wbs').filter(r => r.id !== editId.value), parent_task_id: tasks.filter(r => r.id !== editId.value), next_task_id: tasks.filter(r => r.id !== editId.value),
    predecessor_task_id: tasks, successor_task_id: tasks, linked_task: tasks, task_id: tasks, related_tasks: tasks, affected_tasks: tasks,
    linked_ecr: formKind.value === 'eco' ? choices('ecr').filter(r => records.value.ecr?.find(e => e.id === r.id)?.status === 'APPROVED') : choices('ecr'), related_ecr: choices('ecr'),
    document_id: docs, related_documents: docs, affected_documents: docs, vendor_id: choices('vendors') }
})
function humanError(e: unknown) {
  if (axios.isAxiosError(e) && typeof e.response?.data?.detail?.message === 'string') return e.response.data.detail.message
  return errorMessage(e)
}
async function all<T>(url: string, params: Record<string, string | number> = {}): Promise<T[]> {
  const result: T[] = []
  for (let offset = 0; ; offset += 100) { const batch = (await api.get<T[]>(url, { params: { ...params, offset, limit: 100 } })).data; result.push(...batch); if (batch.length < 100) break }
  return result
}
async function load() {
  loading.value = true; error.value = ''
  try {
    const [metadata, list] = await Promise.all([api.get<ProjectMeta>('/projects/meta'), all<ProjectRow>('/projects')])
    meta.value = metadata.data; projects.value = list
    if (projectId) {
      const [detail, summary, feed, docs, ...groups] = await Promise.all([
        api.get<ProjectRow>(`/projects/${projectId}`), api.get<ProjectDashboard>(`/projects/${projectId}/dashboard`),
        api.get<Activity[]>(`/projects/${projectId}/activity`, { params: { offset: activityPage.value * 50 } }),
        all<Document>('/documents', { scope: 'group' }),
        ...Object.keys(metadata.data.schemas).filter(k => k !== 'projects').map(async kind => ({ kind, rows: await all<ProjectRow>(`/projects/${projectId}/${kind}`) })),
      ])
      project.value = detail.data; dashboard.value = summary.data; activity.value = feed.data; documents.value = docs
      records.value = Object.fromEntries(groups.map(g => [g.kind, g.rows]))
      if (selected.value) selected.value = records.value[tab.value]?.find(r => r.id === selected.value?.id) || null
    }
  } catch (e) { error.value = humanError(e) } finally { loading.value = false }
}
async function switchTab(kind: string) { if (projectId) { await router.replace({ query: { ...route.query, view: kind } }); if (route.query.view !== kind) return } tab.value = kind; selected.value = null; formKind.value = ''; page.value = 0; search.value = ''; statusFilter.value = '' }
function edit(kind: string, row?: ProjectRow) {
  const spec = meta.value?.schemas[kind]; if (!spec) return
  formKind.value = kind; editId.value = row?.id || null; editRevision.value = row?.revision || null
  form.value = Object.fromEntries(Object.entries(spec.properties).map(([key, field]) => [key, row?.[key] ?? field.default ?? (fieldSpec(field).type === 'array' ? [] : fieldSpec(field).type === 'boolean' ? false : field.anyOf?.some(s => s.type === 'null') ? null : '')]))
}
async function save(acknowledge = false) {
  busy.value = true; error.value = ''
  try {
    const base = formKind.value === 'projects' ? '/projects' : `/projects/${projectId}/${formKind.value}`
    const payload = { ...form.value, ...(editId.value ? { revision: editRevision.value } : {}), ...(acknowledge ? { acknowledge_dependencies: true } : {}) }
    const response = editId.value ? await api.put<ProjectRow>(`${base}/${editId.value}`, payload) : await api.post<ProjectRow>(base, payload)
    const wasProject = formKind.value === 'projects'
    formKind.value = ''; message.value = '저장했습니다.'
    if (wasProject && response.data.id !== projectId) await router.push(`/projects/${response.data.id}`)
    else await load()
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.data?.detail?.code === 'DEPENDENCY_WARNING' && !acknowledge) {
      const detail = e.response.data.detail
      if (window.confirm(`${detail.message}\n${detail.warnings.join('\n')}\n확인하고 진행하시겠습니까?`)) { busy.value = false; await save(true); return }
    }
    error.value = humanError(e)
  } finally { busy.value = false }
}
async function archive(kind: string, row: ProjectRow) {
  if (!window.confirm('이 항목을 보관 처리하시겠습니까? 변경 이력은 유지됩니다.')) return
  busy.value = true; error.value = ''
  try { await api.delete(kind === 'projects' ? `/projects/${row.id}` : `/projects/${projectId}/${kind}/${row.id}`, { params: { revision: row.revision } }); selected.value = null; if (kind === 'projects' && projectId === row.id) await router.push('/projects'); else await load() }
  catch (e) { error.value = humanError(e) } finally { busy.value = false }
}
async function seed() {
  busy.value = true; error.value = ''
  try { const { data } = await api.post<ProjectRow>('/projects/seed/karaoke'); await router.push(`/projects/${data.id}`) }
  catch (e) { error.value = humanError(e) } finally { busy.value = false }
}
async function open(kind: string, row: ProjectRow) { await switchTab(kind); if (tab.value === kind) selected.value = row }
async function issueEco(row: ProjectRow) { await switchTab('eco'); edit('eco'); form.value.linked_ecr = row.id; form.value.title = row.title; form.value.affected_tasks = row.affected_tasks || []; form.value.affected_documents = row.affected_documents || [] }
async function addComment() {
  if (!selected.value || !comment.value.trim()) return
  busy.value = true
  try { await api.post(`/projects/${projectId}/comments`, { task_id: selected.value.id, content: comment.value }); comment.value = ''; await load() }
  catch (e) { error.value = humanError(e) } finally { busy.value = false }
}
function display(key: string, value: FieldValue) {
  if (typeof value === 'boolean') return value ? '예' : '아니요'
  if (Array.isArray(value)) return value.map(id => options.value[key]?.find(o => o.id === id)?.name || `#${id}`).join(', ') || '없음'
  if (options.value[key]) return options.value[key]?.find(o => o.id === Number(value))?.name || '미지정'
  return projectLabel(value)
}
const detailFields = computed(() => {
  const fields = meta.value?.schemas[tab.value]?.properties || {}
  if (tab.value !== 'tasks') return fields
  const first = ['purpose', 'completion_criteria', 'instructions', 'materials', 'due_date', 'owner', 'prerequisites']
  return Object.fromEntries(first.filter(k => fields[k]).map(k => [k, fields[k]!]))
})
const extraTaskFields = computed(() => Object.fromEntries(Object.entries(meta.value?.schemas.tasks?.properties || {}).filter(([k]) => !Object.hasOwn(detailFields.value, k) && !['estimated_cost','actual_cost','related_documents'].includes(k))))
const linkedEco = computed(() => tab.value === 'ecr' ? records.value.eco?.find(r => r.linked_ecr === selected.value?.id) : selected.value)
const linkedEcr = computed(() => tab.value === 'eco' ? records.value.ecr?.find(r => r.id === selected.value?.linked_ecr) : selected.value)
const changeSteps = ['요청', '영향 분석', '검토', '승인', '실행', '검증', '종료']
const changeStep = computed(() => linkedEco.value ? ({ OPEN: 4, IMPLEMENTING: 4, VERIFYING: 5, CLOSED: 6, FAILED: 4 }[String(linkedEco.value.implementation_status)] ?? 4) : ({ DRAFT: 0, SUBMITTED: 1, UNDER_REVIEW: 2, APPROVED: 3, REJECTED: 2, CANCELLED: 0 }[String(linkedEcr.value?.status)] ?? 0))
const budgetCommitted = computed(() => (records.value.budget || []).filter(r => records.value.vendors?.some(v => v.id === r.vendor_id && v.status === 'CONTRACTED')).reduce((sum, r) => sum + Number(r.planned_amount || 0), 0))
const schedule = computed(() => [...(records.value.milestones || []).map(row => ({ kind: 'milestones', row, date: String(row.forecast_date || row.planned_date || '') })), ...(records.value.tasks || []).map(row => ({ kind: 'tasks', row, date: String(row.due_date || '') }))].sort((a,b) => (a.date || '9999').localeCompare(b.date || '9999')))
async function newRecord(kind: string) { await switchTab(kind); if (tab.value === kind) edit(kind) }
const money = (value: string | number) => Number(value).toLocaleString('ko-KR') + '원'
onMounted(load)
</script>

<template>
  <div class="project-workspace"><div class="page-heading"><div><p class="eyebrow">PROJECT CONTROL CENTER</p><h1>{{ project ? rowTitle(project) : '프로젝트 관리' }}</h1><p class="muted">현재 상태, 다음 실행 업무와 오픈 위험을 한곳에서 관리하세요.</p></div><RouterLink v-if="project" class="button" to="/projects">프로젝트 목록</RouterLink></div>
  <p v-if="error" class="error" role="alert">{{ error }} <button :disabled="busy" @click="load">새로고침</button></p><p v-if="message" class="success" role="status">{{ message }}</p>
  <p v-if="loading" class="loading" role="status">프로젝트를 불러오는 중입니다…</p>
  <template v-else>
    <header v-if="project && dashboard" class="workspace-header">
      <div class="workspace-context"><span>{{ project.project_code }}</span><span class="status-pill">{{ projectLabel(project.status) }}</span><b :class="`health-${dashboard.summary.health}`">{{ projectLabel(dashboard.summary.health) }}</b><span>진행 {{ dashboard.summary.progress }}%</span><span>{{ project.start_date || '시작일 미정' }} → {{ project.target_end_date || '목표일 미정' }}</span><b>{{ dashboard.summary.d_day == null ? '목표일 미정' : dashboard.summary.d_day >= 0 ? `D-${dashboard.summary.d_day}` : `${-dashboard.summary.d_day}일 지연` }}</b></div>
      <div class="panel-toolbar"><nav class="workspace-nav" aria-label="프로젝트 관리 메뉴"><button v-for="(item, key) in sections" :key="key" :aria-current="section === key ? 'page' : undefined" @click="switchTab(Object.keys(item.tabs)[0]!)">{{ item.label }}</button></nav><div class="button-row"><button class="primary" @click="newRecord('tasks')">새 액션</button><button @click="newRecord('ecr')">변경 요청</button><button v-if="manager" @click="edit('projects', project)">프로젝트 설정</button></div></div>
    </header>
    <nav v-if="project && Object.keys(sections[section]!.tabs).length > 1" class="workspace-subnav" aria-label="세부 관리 메뉴"><button v-for="(label, key) in sections[section]!.tabs" :key="key" :aria-current="tab === key || (tab === 'eco' && key === 'ecr') ? 'page' : undefined" @click="switchTab(key)">{{ label }}</button></nav>
    <div v-if="project && section === 'control' && !selected && !formKind" class="control-summary"><span>열린 위험 <b>{{ (records.risks || []).filter(r => r.status !== 'CLOSED').length }}</b></span><span>미해결 이슈 <b>{{ dashboard?.summary.open_issues }}</b></span><span>검토 중 변경 <b>{{ dashboard?.summary.open_ecr }}</b></span><span>실행 중 변경 <b>{{ dashboard?.summary.active_eco }}</b></span><span>의사결정 <b>{{ records.decisions?.length || 0 }}</b><small> · 확정 기록</small></span></div>
    <section v-if="formKind && schema" class="panel form-panel"><div class="panel-toolbar"><h2>{{ projectTabs[formKind] || '항목' }} {{ editId ? '수정' : '추가' }}</h2><button :disabled="busy" @click="formKind = ''">닫기</button></div><ProjectRecordForm v-model="form" :schema="schema" :options="options" :busy="busy" @save="save()" /><details v-if="formKind === 'projects' && project && editId && manager" class="task-extra"><summary>프로젝트 보관</summary><p class="muted">프로젝트를 목록에서 숨기고 변경 이력을 보존합니다.</p><button class="danger" :disabled="busy" @click="archive('projects', project)">프로젝트 보관</button></details></section>
    <ProjectOverview v-else-if="tab === 'dashboard' && dashboard && project" :project="project" :dashboard="dashboard" :records="records" :activity="activity" @open="open" @navigate="switchTab" />
    <section v-else-if="tab === 'timeline'" class="workspace-section"><h2>프로젝트 일정</h2><p class="muted">업무 마감과 마일스톤을 날짜순으로 확인하세요.</p><p v-if="!schedule.length" class="empty-state">등록된 일정이 없습니다. 업무나 마일스톤에 날짜를 지정하세요.</p><ol class="schedule-list"><li v-for="item in schedule" :key="item.kind + item.row.id"><time>{{ item.date || '일정 미정' }}</time><button @click="open(item.kind, item.row)"><small>{{ projectTabs[item.kind] }} · {{ projectLabel(item.row.status) }}</small><strong>{{ rowTitle(item.row) }}</strong></button></li></ol></section>
    <section v-else-if="tab === 'activity'" class="panel form-panel"><h2>변경 이력</h2><p class="muted">이력은 수정·삭제되지 않습니다.</p><p v-if="!activity.length" class="muted">기록된 활동이 없습니다.</p><details v-for="entry in activity" :key="entry.id" class="activity-entry"><summary>{{ formatDate(entry.created_at) }} · {{ entry.actor_name }} · {{ projectTabs[entry.entity_type] || entry.entity_type }} #{{ entry.entity_id }} · {{ projectLabel(entry.after.status || entry.after.implementation_status || (entry.action.endsWith('ARCHIVED') ? '보관' : '저장')) }}</summary><dl><template v-for="(value, key) in entry.after" :key="key"><template v-if="JSON.stringify(value) !== JSON.stringify(entry.before[key])"><dt>{{ meta?.schemas[entry.entity_type]?.properties[key]?.title || ({revision:'수정 버전',is_deleted:'보관 여부',updated_at:'변경 시각',created_at:'생성 시각'} as Record<string,string>)[key] || key }}</dt><dd>{{ projectLabel(entry.before[key]) }} → {{ projectLabel(value) }}</dd></template></template></dl></details><div class="pagination"><button :disabled="activityPage === 0" @click="activityPage--; load()">이전</button><span>{{ activityPage + 1 }} 페이지</span><button :disabled="activity.length < 50" @click="activityPage++; load()">다음</button></div></section>
    <section v-else-if="selected" class="panel form-panel"><div class="panel-toolbar"><h2>{{ rowTitle(selected) }}</h2><div class="button-row"><button @click="selected = null">목록</button><button @click="edit(tab, selected)">수정</button><button v-if="manager" class="danger" :disabled="busy" @click="archive(tab, selected)">보관</button><button v-if="tab === 'ecr' && selected.status === 'APPROVED' && !linkedEco && manager" class="primary" @click="issueEco(selected)">변경 실행 시작</button></div></div>
      <p class="muted">{{ selected.task_code || selected.ecr_no || selected.eco_no || `#${selected.id}` }} · {{ formatDate(String(selected.updated_at)) }}</p>
      <template v-if="tab === 'ecr' || tab === 'eco'"><ol class="change-stepper" aria-label="변경 진행 단계"><li v-for="(step, i) in changeSteps" :key="step" :class="{ complete: i < changeStep, current: i === changeStep }" :aria-current="i === changeStep ? 'step' : undefined">{{ step }}</li></ol><p class="muted">{{ projectLabel(linkedEcr?.status) }}{{ linkedEco ? ' · ' + projectLabel(linkedEco.implementation_status) : '' }}</p><button v-if="tab === 'ecr' && linkedEco" @click="open('eco', linkedEco)">실행·검증 보기</button><button v-if="tab === 'eco' && linkedEcr" @click="open('ecr', linkedEcr)">요청·승인 보기</button></template>
      <dl class="project-detail"><template v-for="(field, key) in detailFields" :key="key"><dt>{{ field.title }}</dt><dd>{{ display(key, selected[key] ?? null) }}</dd></template></dl>
      <RouterLink v-if="tab === 'documents'" class="button" :to="`/documents/${selected.document_id}`">연결된 문서 열기</RouterLink>
      <template v-if="tab === 'tasks'"><h3>선행 업무</h3><p v-if="!taskDependencies.length" class="muted">등록된 선행 업무가 없습니다.</p><p v-for="dependency in taskDependencies" :key="dependency.id">{{ display('predecessor_task_id', dependency.predecessor_task_id) }} · {{ projectLabel(dependency.dependency_type) }} · 시차 {{ dependency.lag_days }}일</p>
        <h3>비용</h3><p>예상 {{ money(String(selected.estimated_cost || 0)) }} · 실제 {{ money(String(selected.actual_cost || 0)) }}</p>
        <h3>연결된 위험·이슈·변경·결정</h3><p v-if="!related.length" class="muted">연결된 기록이 없습니다.</p><button v-for="link in related" :key="link.kind + link.row.id" class="project-list-button" @click="open(link.kind, link.row)">{{ projectTabs[link.kind] }} · {{ rowTitle(link.row) }}</button>
        <h3>관련 문서</h3><RouterLink v-for="id in (Array.isArray(selected.related_documents) ? selected.related_documents : [])" :key="id" class="project-list-button" :to="`/documents/${id}`">{{ documents.find(d => d.id === id)?.title || '연결된 문서' }}</RouterLink>
        <details class="task-extra"><summary>추가 업무 정보</summary><dl class="project-detail"><template v-for="(field, key) in extraTaskFields" :key="key"><dt>{{ field.title }}</dt><dd>{{ display(key, selected[key] ?? null) }}</dd></template></dl></details>
        <h3>댓글</h3><p v-for="entry in taskComments" :key="entry.id">{{ meta?.members.find(m => m.id === entry.author_id)?.name || '구성원' }} · {{ formatDate(String(entry.created_at)) }}<br />{{ entry.content }}</p><form @submit.prevent="addComment"><label>댓글 내용<textarea v-model="comment" maxlength="10000" required /></label><button :disabled="busy || !comment.trim()">댓글 등록</button></form></template>
      <h3>최근 변경 이력</h3><p v-for="entry in selectedActivity" :key="entry.id">{{ entry.actor_name }} · {{ formatDate(entry.created_at) }} · {{ projectLabel(entry.after.status || entry.after.implementation_status || '저장') }}</p><button @click="switchTab('activity')">전체 변경 이력</button>
    </section>
    <section v-else class="panel form-panel"><div class="panel-toolbar"><h2>{{ tab === 'ecr' ? '변경 관리' : projectTabs[tab] }}</h2><div class="button-row"><button v-if="tab === 'projects'" :disabled="busy" @click="seed">코인노래방 프로젝트 시작</button><button :disabled="busy" class="primary" @click="edit(tab)">추가</button></div></div>
      <div v-if="tab === 'budget' && dashboard" class="budget-summary"><div><span>계획 예산</span><b>{{ money(dashboard.summary.budget) }}</b></div><div><span>계약 업체 배정액</span><b>{{ money(budgetCommitted) }}</b></div><div><span>실제 집행</span><b>{{ money(dashboard.summary.actual_cost) }}</b></div><div><span>잔여 예산</span><b>{{ money(dashboard.summary.budget_variance) }}</b></div><div><span>예산 대비 증감</span><b>{{ money(Number(dashboard.summary.actual_cost) - Number(dashboard.summary.budget)) }}</b></div></div>
      <p v-if="tab === 'budget'" class="muted">계약 업체 배정액은 계약 완료 업체에 연결된 계획 금액입니다. 별도 승인·계약 금액은 현재 기록하지 않습니다.</p>
      <details v-if="tab === 'risks' && dashboard" class="task-extra"><summary>위험도 행렬</summary><p class="muted">가로: 영향도 1→5 · 세로: 가능성 1→5 · 열린 위험 건수</p><div class="risk-grid"><template v-for="(row, p) in dashboard.risk_matrix" :key="p"><div v-for="(count, i) in row" :key="i" :class="(p + 1) * (i + 1) >= 15 ? 'risk-high' : (p + 1) * (i + 1) >= 6 ? 'risk-medium' : 'risk-low'" :title="`가능성 ${p + 1}, 영향도 ${i + 1}: ${count}건`">{{ count }}</div></template></div></details>
      <nav v-if="tab === 'tasks'" class="workspace-subnav" aria-label="업무 실행 단계"><button v-for="(label, key) in { NOW: '지금', NEXT: '다음', WAITING: '대기', ALL: '전체' }" :key="key" :aria-current="workBucket === key ? 'page' : undefined" @click="workBucket = key; page = 0">{{ label }}</button></nav>
      <div class="project-filters"><label>검색<input v-model="search" placeholder="이름 검색" @input="page = 0" /></label><label v-if="statuses.length">상태<select v-model="statusFilter" @change="page = 0"><option value="">전체</option><option v-for="status in statuses" :key="status" :value="status">{{ projectLabel(status) }}</option></select></label></div>
      <p v-if="!filtered.length" class="muted">등록된 항목이 없습니다. 추가 버튼으로 시작하세요.</p>
      <div v-if="tab === 'wbs' && !search && !statusFilter" class="wbs-tree"><button v-for="node in wbsTree" :key="node.row.id" :style="{ paddingLeft: `${Math.min(node.depth, 8) * 20 + 12}px` }" @click="selected = node.row">{{ node.row.wbs_code }} · {{ rowTitle(node.row) }} <span>{{ projectLabel(node.row.status) }} · {{ node.row.progress }}%</span></button></div>
      <div v-else-if="tab === 'tasks'" class="task-list"><button v-for="row in visible" :key="row.id" class="task-card" @click="selected = row"><small>{{ row.task_code }} · {{ projectLabel(row.priority) }}</small><strong>{{ rowTitle(row) }}</strong><span>{{ row.due_date || '마감 미지정' }} · {{ projectLabel(row.status) }} {{ row.critical_path ? '· 핵심 경로' : '' }}</span></button></div>
      <div v-else-if="tab === 'ecr'" class="change-list"><button v-for="row in visible" :key="row.id" class="task-card" @click="selected = row"><small>{{ row.ecr_no }} · {{ projectLabel(row.priority) }}</small><strong>{{ rowTitle(row) }}</strong><span>요청·검토 {{ projectLabel(row.status) }} <template v-if="records.eco?.find(e => e.linked_ecr === row.id)"> → {{ projectLabel(records.eco.find(e => e.linked_ecr === row.id)?.implementation_status) }}</template></span></button></div>
      <div v-else class="table-scroll workspace-table"><table><thead><tr><th>이름</th><th>상태</th><th>담당자</th><th>마감·진행</th><th>주요 지표</th></tr></thead><tbody><tr v-for="row in visible" :key="row.id"><td><RouterLink v-if="tab === 'projects'" :to="`/projects/${row.id}`">{{ rowTitle(row) }}</RouterLink><button v-else class="quiet" @click="selected = row">{{ rowTitle(row) }}</button><small class="muted"> {{ row.task_code || row.project_code || row.ecr_no || row.eco_no }}</small><button v-if="tab === 'projects' && row.id === projectId && manager" @click="edit('projects', row)">설정</button><button v-if="tab === 'projects' && row.id === projectId && manager" class="danger" @click="archive('projects', row)">보관</button></td><td>{{ projectLabel(row.status || row.implementation_status) }}</td><td>{{ display('owner', row.owner || null) }}</td><td>{{ row.due_date || row.planned_date || row.target_end_date || '—' }} <span v-if="row.progress != null"> · {{ row.progress }}%</span></td><td>{{ row.risk_score != null ? `위험 점수 ${row.risk_score}` : row.actual_amount != null ? money(String(row.actual_amount)) : row.critical_path ? '핵심 경로' : '—' }}</td></tr></tbody></table></div>
      <div v-if="tab !== 'wbs' || search || statusFilter" class="pagination"><button :disabled="page === 0" @click="page--">이전</button><span>{{ page + 1 }} 페이지 · {{ filtered.length }}건</span><button :disabled="(page + 1) * 20 >= filtered.length" @click="page++">다음</button></div>
    </section>
  </template>
  </div>
</template>
