from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Money = Annotated[Decimal, Field(ge=0, max_digits=16, decimal_places=2)]
Percent = Annotated[int, Field(ge=0, le=100)]
Priority = Literal['P0', 'P1', 'P2', 'P3']


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, validate_default=True)

    @model_validator(mode='after')
    def dates_in_order(self):
        start = getattr(self, 'start_date', None) or getattr(self, 'implementation_start', None)
        end = getattr(self, 'target_end_date', None) or getattr(self, 'due_date', None) or getattr(self, 'implementation_due', None)
        if start and end and start > end:
            raise ValueError('종료일은 시작일 이후여야 합니다.')
        return self


class ProjectIn(Input):
    project_code: str = Field(default='', max_length=60, title='프로젝트 코드')
    project_name: str = Field(min_length=1, max_length=200, title='프로젝트 이름')
    description: str = Field(default='', max_length=20000, title='설명')
    project_type: str = Field(default='BUSINESS', max_length=50, title='프로젝트 유형')
    owner: int | None = Field(default=None, title='책임자')
    project_manager: int | None = Field(default=None, title='프로젝트 관리자')
    status: Literal['DRAFT', 'PLANNING', 'ACTIVE', 'ON_HOLD', 'AT_RISK', 'COMPLETED', 'CANCELLED'] = Field(default='DRAFT', title='상태')
    priority: Priority = Field(default='P2', title='우선순위')
    start_date: date | None = Field(default=None, title='시작일')
    target_end_date: date | None = Field(default=None, title='목표 종료일')
    actual_end_date: date | None = Field(default=None, title='실제 종료일')
    progress_percent: Percent = Field(default=0, title='진행률')
    health_status: Literal['GREEN', 'YELLOW', 'RED'] = Field(default='GREEN', title='건전성')
    budget: Money = Field(default=0, title='예산 (원)')
    actual_cost: Money = Field(default=0, title='실제 비용 (원)')


class WorkIn(Input):
    title: str = Field(min_length=1, max_length=200, title='제목')
    description: str = Field(default='', max_length=20000, title='설명')
    owner: int | None = Field(default=None, title='담당자')
    priority: Priority = Field(default='P2', title='우선순위')
    status: Literal['BACKLOG', 'READY', 'IN_PROGRESS', 'WAITING', 'BLOCKED', 'REVIEW', 'DONE', 'CANCELLED'] = Field(default='BACKLOG', title='상태')
    progress: Percent = Field(default=0, title='진행률')
    start_date: date | None = Field(default=None, title='시작일')
    due_date: date | None = Field(default=None, title='마감일')


class WbsIn(WorkIn):
    parent_id: int | None = Field(default=None, title='상위 WBS')
    wbs_code: str = Field(default='', max_length=60, title='WBS 코드')
    actual_end_date: date | None = Field(default=None, title='실제 종료일')
    sort_order: int = Field(default=0, ge=0, title='정렬 순서')


class TaskIn(WorkIn):
    task_code: str = Field(default='', max_length=60, title='업무 코드')
    task_type: Literal['TASK', 'SUBTASK', 'ACTION', 'CHECKPOINT'] = Field(default='ACTION', title='업무 유형')
    wbs_id: int | None = Field(default=None, title='WBS')
    parent_task_id: int | None = Field(default=None, title='상위 업무')
    estimated_hours: Annotated[Decimal, Field(ge=0, le=1000000)] = Field(default=0, title='예상 시간')
    actual_hours: Annotated[Decimal, Field(ge=0, le=1000000)] = Field(default=0, title='실제 시간')
    estimated_cost: Money = Field(default=0, title='예상 비용 (원)')
    actual_cost: Money = Field(default=0, title='실제 비용 (원)')
    blocker: str = Field(default='', max_length=5000, title='진행을 막는 사항')
    critical_path: bool = Field(default=False, title='핵심 경로')
    approval_required: bool = Field(default=False, title='완료 승인 필요')
    purpose: str = Field(default='', max_length=5000, title='목적')
    prerequisites: str = Field(default='', max_length=5000, title='선행조건')
    materials: str = Field(default='', max_length=5000, title='준비물')
    instructions: str = Field(default='', max_length=20000, title='실행방법')
    location: str = Field(default='', max_length=1000, title='관련 장소')
    website: str = Field(default='', max_length=2000, title='사이트')
    organization: str = Field(default='', max_length=500, title='담당 기관')
    contact: str = Field(default='', max_length=1000, title='연락처')
    required_documents: str = Field(default='', max_length=5000, title='필요 서류')
    questions: str = Field(default='', max_length=5000, title='질문할 내용')
    completion_criteria: str = Field(default='', max_length=5000, title='완료 기준')
    completion_report: str = Field(default='', max_length=10000, title='완료 후 보고사항')
    next_task_id: int | None = Field(default=None, title='다음 연결 업무')
    related_documents: list[int] = Field(default_factory=list, max_length=100, title='관련 문서')


class DependencyIn(Input):
    predecessor_task_id: int = Field(title='선행 업무')
    successor_task_id: int = Field(title='후속 업무')
    dependency_type: Literal['FS', 'SS', 'FF', 'SF'] = Field(default='FS', title='의존성 유형')
    lag_days: int = Field(default=0, ge=-3650, le=3650, title='시차 (일)')


class EcrIn(Input):
    title: str = Field(min_length=1, max_length=200, title='변경 요청 제목')
    description: str = Field(default='', max_length=20000, title='변경 내용')
    reason: str = Field(min_length=1, max_length=5000, title='변경 사유')
    category: str = Field(default='SCOPE', max_length=80, title='분류')
    priority: Priority = Field(default='P2', title='우선순위')
    impact_schedule: str = Field(default='', max_length=5000, title='일정 영향')
    impact_cost: Annotated[Decimal, Field(max_digits=16, decimal_places=2)] = Field(default=0, title='비용 증감 (원)')
    impact_scope: str = Field(default='', max_length=5000, title='범위 영향')
    impact_quality: str = Field(default='', max_length=5000, title='품질 영향')
    impact_risk: str = Field(default='', max_length=5000, title='위험 영향')
    affected_tasks: list[int] = Field(default_factory=list, max_length=100, title='영향받는 업무')
    affected_documents: list[int] = Field(default_factory=list, max_length=100, title='영향받는 문서')
    status: Literal['DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'CANCELLED'] = Field(default='DRAFT', title='상태')
    reviewer: int | None = Field(default=None, title='검토자')
    review_comment: str = Field(default='', max_length=5000, title='검토 의견')
    decision: str = Field(default='', max_length=5000, title='승인·반려 근거')


class EcoIn(Input):
    linked_ecr: int = Field(title='승인된 변경 요청')
    title: str = Field(min_length=1, max_length=200, title='변경 지시 제목')
    implementation_plan: str = Field(min_length=1, max_length=20000, title='실행 계획')
    owner: int | None = Field(default=None, title='담당자')
    implementation_start: date | None = Field(default=None, title='실행 시작일')
    implementation_due: date | None = Field(default=None, title='실행 마감일')
    affected_tasks: list[int] = Field(default_factory=list, max_length=100, title='영향받는 업무')
    affected_documents: list[int] = Field(default_factory=list, max_length=100, title='영향받는 문서')
    before_state: str = Field(default='', max_length=10000, title='변경 전')
    after_state: str = Field(default='', max_length=10000, title='변경 후')
    implementation_status: Literal['OPEN', 'IMPLEMENTING', 'VERIFYING', 'CLOSED', 'FAILED'] = Field(default='OPEN', title='실행 상태')
    verification_result: str = Field(default='', max_length=10000, title='검증 결과')


class IssueIn(Input):
    title: str = Field(min_length=1, max_length=200, title='이슈 제목')
    description: str = Field(default='', max_length=20000, title='설명')
    severity: Literal['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] = Field(default='MEDIUM', title='심각도')
    owner: int | None = Field(default=None, title='담당자')
    due_date: date | None = Field(default=None, title='해결 기한')
    status: Literal['OPEN', 'INVESTIGATING', 'ACTION_REQUIRED', 'RESOLVED', 'CLOSED'] = Field(default='OPEN', title='상태')
    root_cause: str = Field(default='', max_length=5000, title='근본 원인')
    corrective_action: str = Field(default='', max_length=5000, title='시정 조치')
    linked_task: int | None = Field(default=None, title='관련 업무')
    linked_ecr: int | None = Field(default=None, title='관련 변경 요청')
    resolution: str = Field(default='', max_length=5000, title='해결 내용')


class RiskIn(Input):
    title: str = Field(min_length=1, max_length=200, title='위험 제목')
    description: str = Field(default='', max_length=20000, title='설명')
    category: str = Field(default='', max_length=80, title='분류')
    probability: int = Field(default=1, ge=1, le=5, title='발생 가능성 (1~5)')
    impact: int = Field(default=1, ge=1, le=5, title='영향도 (1~5)')
    owner: int | None = Field(default=None, title='담당자')
    mitigation: str = Field(default='', max_length=5000, title='완화 대책')
    contingency: str = Field(default='', max_length=5000, title='비상 대책')
    trigger: str = Field(default='', max_length=5000, title='발생 징후')
    status: Literal['OPEN', 'MITIGATING', 'ACCEPTED', 'CLOSED'] = Field(default='OPEN', title='상태')
    linked_task: int | None = Field(default=None, title='관련 업무')


class DecisionIn(Input):
    title: str = Field(min_length=1, max_length=200, title='의사결정 제목')
    context: str = Field(default='', max_length=10000, title='배경')
    options_considered: str = Field(default='', max_length=10000, title='검토한 대안')
    decision: str = Field(min_length=1, max_length=10000, title='결정 내용')
    rationale: str = Field(min_length=1, max_length=10000, title='결정 근거')
    related_tasks: list[int] = Field(default_factory=list, max_length=100, title='관련 업무')
    related_ecr: int | None = Field(default=None, title='관련 변경 요청')
    related_documents: list[int] = Field(default_factory=list, max_length=100, title='관련 문서')


class MilestoneIn(Input):
    milestone_code: str = Field(default='', max_length=60, title='마일스톤 코드')
    name: str = Field(min_length=1, max_length=200, title='마일스톤 이름')
    planned_date: date | None = Field(default=None, title='계획일')
    forecast_date: date | None = Field(default=None, title='예상일')
    actual_date: date | None = Field(default=None, title='실제 완료일')
    status: Literal['PLANNED', 'IN_PROGRESS', 'AT_RISK', 'COMPLETED', 'CANCELLED'] = Field(default='PLANNED', title='상태')
    owner: int | None = Field(default=None, title='담당자')
    completion_condition: str = Field(default='', max_length=5000, title='완료 조건')


class BudgetIn(Input):
    title: str = Field(min_length=1, max_length=200, title='예산 항목')
    category: str = Field(default='', max_length=80, title='분류')
    planned_amount: Money = Field(default=0, title='계획 금액 (원)')
    actual_amount: Money = Field(default=0, title='집행 금액 (원)')
    vendor_id: int | None = Field(default=None, title='거래처')
    linked_task: int | None = Field(default=None, title='관련 업무')
    notes: str = Field(default='', max_length=5000, title='비고')


class VendorIn(Input):
    name: str = Field(min_length=1, max_length=200, title='업체 이름')
    category: str = Field(default='', max_length=80, title='업종')
    contact: str = Field(default='', max_length=1000, title='담당자·연락처')
    website: str = Field(default='', max_length=2000, title='사이트')
    status: Literal['CANDIDATE', 'SELECTED', 'CONTRACTED', 'INACTIVE'] = Field(default='CANDIDATE', title='상태')
    notes: str = Field(default='', max_length=10000, title='비고')


class ProjectDocumentIn(Input):
    document_id: int = Field(title='그룹 문서')
    notes: str = Field(default='', max_length=5000, title='연결 사유')


class ReadinessIn(Input):
    category: Literal['LEGAL', 'LOCATION', 'CONSTRUCTION', 'FIRE', 'ELECTRICAL', 'SOUNDPROOF', 'EQUIPMENT', 'PAYMENT', 'IT', 'SECURITY', 'ACCOUNTING', 'STAFF', 'SOP', 'MARKETING'] = Field(title='준비 영역')
    status: Literal['NOT_STARTED', 'IN_PROGRESS', 'BLOCKED', 'READY'] = Field(default='NOT_STARTED', title='상태')
    owner: int | None = Field(default=None, title='담당자')
    notes: str = Field(default='', max_length=10000, title='확인 사항·증빙')


class CommentIn(Input):
    task_id: int = Field(title='업무')
    content: str = Field(min_length=1, max_length=10000, title='댓글')


SCHEMAS = {'projects': ProjectIn, 'wbs': WbsIn, 'tasks': TaskIn, 'dependencies': DependencyIn,
           'ecr': EcrIn, 'eco': EcoIn, 'issues': IssueIn, 'risks': RiskIn,
           'decisions': DecisionIn, 'milestones': MilestoneIn, 'budget': BudgetIn,
           'vendors': VendorIn, 'documents': ProjectDocumentIn, 'readiness': ReadinessIn, 'comments': CommentIn}
