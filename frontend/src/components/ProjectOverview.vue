<script setup lang="ts">
import { computed } from 'vue'
import { formatDate } from '../types'
import { projectLabel, rowTitle, projectTabs, type ProjectRow, type ProjectDashboard, type Activity } from '../types/projects'
const props = defineProps<{ project: ProjectRow; dashboard: ProjectDashboard; records: Record<string, ProjectRow[]>; activity: Activity[] }>()
const emit = defineEmits<{ open: [kind: string, row: ProjectRow]; navigate: [kind: string] }>()
const money = (n: string | number) => Number(n).toLocaleString('ko-KR') + '원'
const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul' }).format(new Date())
const attention = computed(() => [
  ...props.dashboard.overdue.map(row => ({ kind: 'tasks', row, reason: '기한 초과' })),
  ...(props.records.tasks || []).filter(r => ['BLOCKED', 'WAITING'].includes(String(r.status))).map(row => ({ kind: 'tasks', row, reason: '진행 대기' })),
  ...(props.records.risks || []).filter(r => r.status !== 'CLOSED' && Number(r.risk_score) >= 15).map(row => ({ kind: 'risks', row, reason: '고위험' })),
  ...(props.records.issues || []).filter(r => !['CLOSED', 'RESOLVED'].includes(String(r.status)) && ['HIGH', 'CRITICAL'].includes(String(r.severity))).map(row => ({ kind: 'issues', row, reason: '중요 이슈' })),
  ...props.dashboard.changes.map(row => ({ kind: 'ecr', row, reason: '변경 검토' })),
  ...props.dashboard.milestones.filter(r => milestoneState(r) === '지연').map(row => ({ kind: 'milestones', row, reason: '일정 지연' })),
].filter((item, i, all) => all.findIndex(x => x.kind === item.kind && x.row.id === item.row.id) === i))
function milestoneState(r: ProjectRow) {
  if (r.status === 'COMPLETED') return '완료'
  if (r.status === 'CANCELLED') return '취소'
  if (r.status === 'AT_RISK' || String(r.forecast_date || r.planned_date || '9999') < today || (r.forecast_date && r.planned_date && String(r.forecast_date) > String(r.planned_date))) return '지연'
  return r.status === 'IN_PROGRESS' ? '진행 중' : '예정'
}
</script>

<template>
  <section class="workspace-status" aria-label="프로젝트 현황">
    <div><span>전체 진행률</span><strong>{{ dashboard.summary.progress }}<small>%</small></strong><progress :value="dashboard.summary.progress" max="100" aria-label="전체 진행률" /></div>
    <div><span>목표일까지</span><strong>{{ dashboard.summary.d_day == null ? '미지정' : dashboard.summary.d_day >= 0 ? `D-${dashboard.summary.d_day}` : `${-dashboard.summary.d_day}일 지연` }}</strong></div>
    <div><span>건전성</span><strong :class="`health-${dashboard.summary.health}`">{{ projectLabel(dashboard.summary.health) }}</strong></div>
    <div><span>목표 오픈</span><b>{{ project.target_end_date || '일정 미정' }}</b></div>
    <div><span>예산</span><b>{{ money(dashboard.summary.budget) }}</b></div>
    <button class="quiet" @click="emit('navigate', 'readiness')"><span>오픈 준비도</span><strong>{{ dashboard.summary.readiness }}%</strong></button>
  </section>
  <section class="workspace-section next-actions">
    <div class="panel-toolbar"><div><p class="eyebrow">NEXT ACTION</p><h2>지금 해야 할 일</h2></div><button @click="emit('navigate', 'tasks')">전체 업무</button></div>
    <p v-if="!dashboard.next_actions.length" class="empty-state">바로 실행할 업무가 없습니다. 새 액션을 등록하거나 대기 조건을 확인하세요.</p>
    <button v-for="(task, i) in dashboard.next_actions.slice(0, 3)" :key="task.id" class="next-action" :class="{ 'action-hero': i === 0 }" @click="emit('open', 'tasks', task)"><small>{{ i === 0 ? '가장 먼저 실행하세요' : '이어서 할 일' }} · {{ task.task_code }}</small><strong>{{ rowTitle(task) }}</strong><span>{{ projectLabel(task.priority) }} · {{ task.due_date || '마감 미지정' }} {{ task.critical_path ? '· 핵심 경로' : '' }}</span></button>
  </section>
  <section class="workspace-section attention" :class="{ 'needs-attention': attention.length }">
    <h2>확인이 필요한 사항 <small>{{ attention.length }}건</small></h2><p v-if="!attention.length" class="muted">현재 확인이 필요한 문제가 없습니다.</p>
    <details v-else :open="attention.length <= 5"><summary>{{ attention.length }}건의 위험·지연·변경 확인</summary><button v-for="item in attention" :key="item.kind + item.row.id" class="project-list-button" @click="emit('open', item.kind, item.row)"><span class="status-pill">{{ item.reason }}</span> {{ rowTitle(item.row) }}</button></details>
  </section>
  <section class="workspace-section"><div class="panel-toolbar"><h2>주요 일정</h2><button @click="emit('navigate', 'timeline')">일정 계획</button></div><p v-if="!dashboard.milestones.length" class="empty-state">마일스톤을 등록하면 오픈까지의 주요 일정이 표시됩니다.</p><ol class="milestone-strip"><li v-for="row in dashboard.milestones" :key="row.id"><button @click="emit('open', 'milestones', row)"><span class="status-pill" :class="{ 'health-RED': milestoneState(row) === '지연', 'health-GREEN': milestoneState(row) === '완료' }">{{ milestoneState(row) }}</span><strong>{{ rowTitle(row) }}</strong><small>{{ row.forecast_date || row.planned_date || '일정 미정' }}</small></button></li></ol></section>
  <section class="workspace-section"><div class="panel-toolbar"><h2>분야별 진행률</h2><button @click="emit('navigate', 'wbs')">전체 WBS</button></div><p v-if="!records.wbs?.length" class="empty-state">WBS를 등록하여 분야별 진행 상황을 관리하세요.</p><div class="workstream-grid"><button v-for="row in (records.wbs || []).filter(r => !r.parent_id)" :key="row.id" @click="emit('open', 'wbs', row)"><span>{{ rowTitle(row) }} <b>{{ row.progress }}%</b></span><progress :value="Number(row.progress)" max="100" :aria-label="rowTitle(row)" /></button></div></section>
  <section class="workspace-section"><div class="panel-toolbar"><h2>오픈 준비도 <strong>{{ dashboard.summary.readiness }}%</strong></h2><button @click="emit('navigate', 'readiness')">체크리스트</button></div><p v-if="!records.readiness?.length" class="empty-state">준비 영역별 확인 사항과 증빙을 등록하세요.</p><div class="readiness-grid"><button v-for="row in records.readiness" :key="row.id" @click="emit('open', 'readiness', row)"><span>{{ rowTitle(row) }}</span><b :class="row.status === 'READY' ? 'health-GREEN' : row.status === 'BLOCKED' ? 'health-RED' : 'muted'">{{ projectLabel(row.status) }}</b></button></div></section>
  <section class="workspace-section"><div class="panel-toolbar"><h2>최근 활동</h2><button @click="emit('navigate', 'activity')">전체 이력</button></div><p v-if="!activity.length" class="muted">아직 기록된 활동이 없습니다.</p><p v-for="entry in activity.slice(0, 5)" :key="entry.id" class="activity-line"><b>{{ entry.actor_name }}</b> · {{ projectTabs[entry.entity_type] }} · {{ projectLabel(entry.after.status || entry.after.implementation_status || (entry.action.endsWith('ARCHIVED') ? '보관' : '저장')) }}<small>{{ formatDate(entry.created_at) }}</small></p></section>
</template>
