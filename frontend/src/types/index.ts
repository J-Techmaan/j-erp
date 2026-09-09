export interface User { id: number; username: string; display_name: string; profile_image_url: string | null; is_active: boolean }
export interface CurrentUser extends User { email: string | null }
export type GroupRole = 'OWNER' | 'MEMBER'
export type MembershipStatus = 'PENDING' | 'ACTIVE' | 'REJECTED'
export interface Membership { id: number; user: User; role: GroupRole; is_admin: boolean; status: MembershipStatus; created_at: string }
export interface Group { id: number; name: string; code: string; owner_id: number; my_role: GroupRole | null; members: Membership[]; created_at: string; updated_at: string }
export type ApprovalType = 'APPROVAL' | 'AGREEMENT' | 'NOTIFICATION'
export type DocumentStatus = 'DRAFT' | 'IN_PROGRESS' | 'COMPLETED' | 'REJECTED' | 'CANCELLED'
export type StepStatus = 'WAITING' | 'CURRENT' | 'APPROVED' | 'REJECTED' | 'NOTIFIED'
export interface StepInput { user_id: number; approval_type: ApprovalType }
export interface Step extends StepInput { id: number; user: User; step_order: number; status: StepStatus; comment: string | null; acted_at: string | null }
export interface Attachment { id: number; original_filename: string; file_size: number; mime_type: string; created_at: string }
export interface ApprovalAction { id: number; user: User; round_number: number; action: string; comment: string | null; acted_at: string }
export interface Document { id: number; group_id: number | null; document_number: string; title: string; content: string; author_id: number; author: User; status: DocumentStatus; revision: number; round_number: number; created_at: string; updated_at: string; submitted_at: string | null; completed_at: string | null; rejected_at: string | null; cancelled_at: string | null; rejector_id: number | null; rejector: User | null; source_document_id: number | null; steps: Step[]; attachments: Attachment[]; history: ApprovalAction[] }
export interface DocumentInput { title: string; content: string; steps: StepInput[]; revision?: number }
export interface ScheduleInput { title: string; description: string; start_at: string; end_at: string; all_day: boolean }
export interface Schedule extends ScheduleInput { id: number; user_id: number; group_id: number | null; created_at: string; updated_at: string }
export const documentLabels: Record<DocumentStatus, string> = { DRAFT: '기안', IN_PROGRESS: '상신중', COMPLETED: '완결', REJECTED: '반려', CANCELLED: '취소됨' }
export const typeLabels: Record<ApprovalType, string> = { APPROVAL: '결재', AGREEMENT: '합의', NOTIFICATION: '통보' }
export const stepLabels: Record<StepStatus, string> = { WAITING: '대기', CURRENT: '결재중', APPROVED: '승인', REJECTED: '반려', NOTIFIED: '통보 완료' }
export function formatDate(value: string | null) { return value ? new Date(value).toLocaleString('ko-KR', { dateStyle: 'medium', timeStyle: 'short' }) : '—' }
