export type FieldValue = string | number | boolean | null | number[]
export interface ProjectRow { [key: string]: FieldValue; id: number; revision: number }
export interface FieldSchema {
  title?: string; type?: string; format?: string; default?: FieldValue; enum?: string[]
  anyOf?: FieldSchema[]; maxLength?: number; minLength?: number; minimum?: number; maximum?: number
}
export interface RecordSchema { properties: Record<string, FieldSchema>; required?: string[] }
export interface Option { id: number; name: string }
export interface ProjectMeta { schemas: Record<string, RecordSchema>; members: Option[] }
export interface Activity { id: number; actor_name: string; entity_type: string; entity_id: number; action: string; created_at: string; before: Record<string, FieldValue>; after: Record<string, FieldValue> }
export interface ProjectDashboard {
  project: ProjectRow
  summary: { progress: number; d_day: number | null; health: string; open_tasks: number; overdue_tasks: number; blocked_tasks: number; critical_tasks: number; open_issues: number; high_risks: number; open_ecr: number; active_eco: number; budget: string; actual_cost: string; budget_variance: string; readiness: number }
  next_actions: ProjectRow[]; buckets: Record<string, ProjectRow[]>; overdue: ProjectRow[]; critical: ProjectRow[]
  risk_matrix: number[][]; milestones: ProjectRow[]; changes: ProjectRow[]; ecos: ProjectRow[]; decisions: ProjectRow[]
}
export const projectTabs: Record<string, string> = { dashboard: '프로젝트 대시보드', projects: '프로젝트', wbs: 'WBS', tasks: '업무·액션', dependencies: '업무 의존성', ecr: '변경 요청 (ECR)', eco: '변경 지시 (ECO)', issues: '이슈', risks: '위험', decisions: '의사결정', milestones: '마일스톤', budget: '예산', vendors: '업체', documents: '관련 문서', readiness: '오픈 준비도', activity: '활동 이력' }
export const projectLabels: Record<string, string> = {
  DRAFT: '초안', PLANNING: '계획 중', ACTIVE: '진행 중', ON_HOLD: '보류', AT_RISK: '위험', COMPLETED: '완료', CANCELLED: '취소',
  GREEN: '정상', YELLOW: '주의', RED: '위험', BACKLOG: '미착수', READY: '준비 완료', IN_PROGRESS: '진행 중', WAITING: '대기', BLOCKED: '진행 불가', REVIEW: '완료 검토', DONE: '완료',
  TASK: '업무', SUBTASK: '하위 업무', ACTION: '실행 액션', CHECKPOINT: '점검', SUBMITTED: '검토 요청', UNDER_REVIEW: '검토 중', APPROVED: '승인', REJECTED: '반려',
  OPEN: '미해결', IMPLEMENTING: '변경 실행 중', VERIFYING: '검증 중', CLOSED: '종료', FAILED: '실패',
  LOW: '낮음', MEDIUM: '보통', HIGH: '높음', CRITICAL: '매우 높음', INVESTIGATING: '조사 중', ACTION_REQUIRED: '조치 필요', RESOLVED: '해결', MITIGATING: '완화 중', ACCEPTED: '수용',
  PLANNED: '계획', CANDIDATE: '후보', SELECTED: '선정', CONTRACTED: '계약 완료', INACTIVE: '비활성',
  LEGAL: '법무·인허가', LOCATION: '점포', CONSTRUCTION: '공사', FIRE: '소방', ELECTRICAL: '전기', SOUNDPROOF: '방음', EQUIPMENT: '장비', PAYMENT: '결제', IT: 'IT', SECURITY: '보안', ACCOUNTING: '회계', STAFF: '인력', SOP: '운영 절차', MARKETING: '마케팅', NOT_STARTED: '미착수',
  NOW: '지금 할 일', NEXT: '다음 할 일', LATER: '나중에 할 일', FS: '완료 후 시작', SS: '시작 후 시작', FF: '완료 후 완료', SF: '시작 후 완료',
  P0: 'P0 · 최우선', P1: 'P1 · 높음', P2: 'P2 · 보통', P3: 'P3 · 낮음', BUSINESS: '사업', OPENING: '매장 오픈', SCOPE: '범위',
}
export function projectLabel(value: FieldValue | undefined) { return value == null ? '미지정' : projectLabels[String(value)] || String(value) }
export function rowTitle(row: ProjectRow) { return String(row.project_name || row.title || row.name || row.document_title || projectLabels[String(row.category)] || row.category || `#${row.id}`) }
export function fieldSpec(field: FieldSchema): FieldSchema { return field.anyOf?.find(item => item.type !== 'null') || field }
