from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, declared_attr

from app.core.database import Base
from app.models import Timestamps, now


class ProjectRecord(Timestamps):
    id: Mapped[int] = mapped_column(primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    @declared_attr.directive
    def __mapper_args__(cls):
        return {'version_id_col': cls.revision}


class Project(ProjectRecord, Base):
    __tablename__ = 'projects'
    group_id: Mapped[int] = mapped_column(ForeignKey('groups.id'), index=True)
    __table_args__ = (UniqueConstraint('group_id', 'project_code'),)
    project_code: Mapped[str] = mapped_column(String(60))
    project_name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default='')
    project_type: Mapped[str] = mapped_column(String(50), default='BUSINESS')
    owner: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), index=True, default=None)
    project_manager: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), index=True, default=None)
    status: Mapped[str] = mapped_column(Text, default='DRAFT', index=True)
    priority: Mapped[str] = mapped_column(Text, default='P2')
    start_date: Mapped[date | None] = mapped_column(Date, default=None)
    target_end_date: Mapped[date | None] = mapped_column(Date, default=None)
    actual_end_date: Mapped[date | None] = mapped_column(Date, default=None)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    health_status: Mapped[str] = mapped_column(Text, default='GREEN')
    budget: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    actual_cost: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)

class Wbs(ProjectRecord, Base):
    __tablename__ = 'project_wbs'
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    __table_args__ = (UniqueConstraint('project_id', 'wbs_code'),)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default='')
    owner: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), index=True, default=None)
    priority: Mapped[str] = mapped_column(Text, default='P2')
    status: Mapped[str] = mapped_column(Text, default='BACKLOG', index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    start_date: Mapped[date | None] = mapped_column(Date, default=None)
    due_date: Mapped[date | None] = mapped_column(Date, default=None, index=True)
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('project_wbs.id'), index=True, default=None)
    wbs_code: Mapped[str] = mapped_column(String(60))
    actual_end_date: Mapped[date | None] = mapped_column(Date, default=None)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

class Task(ProjectRecord, Base):
    __tablename__ = 'project_tasks'
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    __table_args__ = (UniqueConstraint('project_id', 'task_code'),)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default='')
    owner: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), index=True, default=None)
    priority: Mapped[str] = mapped_column(Text, default='P2')
    status: Mapped[str] = mapped_column(Text, default='BACKLOG', index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    start_date: Mapped[date | None] = mapped_column(Date, default=None)
    due_date: Mapped[date | None] = mapped_column(Date, default=None, index=True)
    task_code: Mapped[str] = mapped_column(String(60))
    task_type: Mapped[str] = mapped_column(Text, default='ACTION')
    wbs_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('project_wbs.id'), index=True, default=None)
    parent_task_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('project_tasks.id'), index=True, default=None)
    estimated_hours: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    actual_hours: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    actual_cost: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    blocker: Mapped[str] = mapped_column(Text, default='')
    critical_path: Mapped[bool] = mapped_column(Boolean, default=False)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False)
    purpose: Mapped[str] = mapped_column(Text, default='')
    prerequisites: Mapped[str] = mapped_column(Text, default='')
    materials: Mapped[str] = mapped_column(Text, default='')
    instructions: Mapped[str] = mapped_column(Text, default='')
    location: Mapped[str] = mapped_column(String(1000), default='')
    website: Mapped[str] = mapped_column(String(2000), default='')
    organization: Mapped[str] = mapped_column(String(500), default='')
    contact: Mapped[str] = mapped_column(String(1000), default='')
    required_documents: Mapped[str] = mapped_column(Text, default='')
    questions: Mapped[str] = mapped_column(Text, default='')
    completion_criteria: Mapped[str] = mapped_column(Text, default='')
    completion_report: Mapped[str] = mapped_column(Text, default='')
    next_task_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('project_tasks.id'), index=True, default=None)
    related_documents: Mapped[list[int]] = mapped_column(JSON, default=list)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

class TaskDependency(ProjectRecord, Base):
    __tablename__ = 'project_dependencies'
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    __table_args__ = (UniqueConstraint('project_id', 'predecessor_task_id', 'successor_task_id'),)
    predecessor_task_id: Mapped[int] = mapped_column(Integer, ForeignKey('project_tasks.id'), index=True)
    successor_task_id: Mapped[int] = mapped_column(Integer, ForeignKey('project_tasks.id'), index=True)
    dependency_type: Mapped[str] = mapped_column(Text, default='FS')
    lag_days: Mapped[int] = mapped_column(Integer, default=0)

class Ecr(ProjectRecord, Base):
    __tablename__ = 'project_ecr'
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default='')
    reason: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(80), default='SCOPE')
    priority: Mapped[str] = mapped_column(Text, default='P2')
    impact_schedule: Mapped[str] = mapped_column(Text, default='')
    impact_cost: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    impact_scope: Mapped[str] = mapped_column(Text, default='')
    impact_quality: Mapped[str] = mapped_column(Text, default='')
    impact_risk: Mapped[str] = mapped_column(Text, default='')
    affected_tasks: Mapped[list[int]] = mapped_column(JSON, default=list)
    affected_documents: Mapped[list[int]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(Text, default='DRAFT', index=True)
    reviewer: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), index=True, default=None)
    review_comment: Mapped[str] = mapped_column(Text, default='')
    decision: Mapped[str] = mapped_column(Text, default='')
    ecr_no: Mapped[str] = mapped_column(String(60), unique=True)
    requester: Mapped[int] = mapped_column(ForeignKey('users.id'))
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=now)

class Eco(ProjectRecord, Base):
    __tablename__ = 'project_eco'
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    __table_args__ = (UniqueConstraint('project_id', 'linked_ecr'),)
    linked_ecr: Mapped[int] = mapped_column(Integer, ForeignKey('project_ecr.id'), index=True)
    title: Mapped[str] = mapped_column(String(200))
    implementation_plan: Mapped[str] = mapped_column(Text)
    owner: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), index=True, default=None)
    implementation_start: Mapped[date | None] = mapped_column(Date, default=None)
    implementation_due: Mapped[date | None] = mapped_column(Date, default=None)
    affected_tasks: Mapped[list[int]] = mapped_column(JSON, default=list)
    affected_documents: Mapped[list[int]] = mapped_column(JSON, default=list)
    before_state: Mapped[str] = mapped_column(Text, default='')
    after_state: Mapped[str] = mapped_column(Text, default='')
    implementation_status: Mapped[str] = mapped_column(Text, default='OPEN', index=True)
    verification_result: Mapped[str] = mapped_column(Text, default='')
    eco_no: Mapped[str] = mapped_column(String(60), unique=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

class Issue(ProjectRecord, Base):
    __tablename__ = 'project_issues'
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default='')
    severity: Mapped[str] = mapped_column(Text, default='MEDIUM')
    owner: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), index=True, default=None)
    due_date: Mapped[date | None] = mapped_column(Date, default=None, index=True)
    status: Mapped[str] = mapped_column(Text, default='OPEN', index=True)
    root_cause: Mapped[str] = mapped_column(Text, default='')
    corrective_action: Mapped[str] = mapped_column(Text, default='')
    linked_task: Mapped[int | None] = mapped_column(Integer, ForeignKey('project_tasks.id'), index=True, default=None)
    linked_ecr: Mapped[int | None] = mapped_column(Integer, ForeignKey('project_ecr.id'), index=True, default=None)
    resolution: Mapped[str] = mapped_column(Text, default='')
    issue_no: Mapped[str] = mapped_column(String(60), unique=True)
    detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=now)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

class Risk(ProjectRecord, Base):
    __tablename__ = 'project_risks'
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default='')
    category: Mapped[str] = mapped_column(String(80), default='')
    probability: Mapped[int] = mapped_column(Integer, default=1)
    impact: Mapped[int] = mapped_column(Integer, default=1)
    owner: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), index=True, default=None)
    mitigation: Mapped[str] = mapped_column(Text, default='')
    contingency: Mapped[str] = mapped_column(Text, default='')
    trigger: Mapped[str] = mapped_column(Text, default='')
    status: Mapped[str] = mapped_column(Text, default='OPEN', index=True)
    linked_task: Mapped[int | None] = mapped_column(Integer, ForeignKey('project_tasks.id'), index=True, default=None)
    risk_no: Mapped[str] = mapped_column(String(60), unique=True)

class Decision(ProjectRecord, Base):
    __tablename__ = 'project_decisions'
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    title: Mapped[str] = mapped_column(String(200))
    context: Mapped[str] = mapped_column(Text, default='')
    options_considered: Mapped[str] = mapped_column(Text, default='')
    decision: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text)
    related_tasks: Mapped[list[int]] = mapped_column(JSON, default=list)
    related_ecr: Mapped[int | None] = mapped_column(Integer, ForeignKey('project_ecr.id'), index=True, default=None)
    related_documents: Mapped[list[int]] = mapped_column(JSON, default=list)
    decision_no: Mapped[str] = mapped_column(String(60), unique=True)
    decided_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=now)

class Milestone(ProjectRecord, Base):
    __tablename__ = 'project_milestones'
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    __table_args__ = (UniqueConstraint('project_id', 'milestone_code'),)
    milestone_code: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(200))
    planned_date: Mapped[date | None] = mapped_column(Date, default=None)
    forecast_date: Mapped[date | None] = mapped_column(Date, default=None)
    actual_date: Mapped[date | None] = mapped_column(Date, default=None)
    status: Mapped[str] = mapped_column(Text, default='PLANNED', index=True)
    owner: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), index=True, default=None)
    completion_condition: Mapped[str] = mapped_column(Text, default='')

class BudgetEntry(ProjectRecord, Base):
    __tablename__ = 'project_budget'
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(80), default='')
    planned_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    actual_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    vendor_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('project_vendors.id'), index=True, default=None)
    linked_task: Mapped[int | None] = mapped_column(Integer, ForeignKey('project_tasks.id'), index=True, default=None)
    notes: Mapped[str] = mapped_column(Text, default='')

class Vendor(ProjectRecord, Base):
    __tablename__ = 'project_vendors'
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(80), default='')
    contact: Mapped[str] = mapped_column(String(1000), default='')
    website: Mapped[str] = mapped_column(String(2000), default='')
    status: Mapped[str] = mapped_column(Text, default='CANDIDATE', index=True)
    notes: Mapped[str] = mapped_column(Text, default='')

class ProjectDocument(ProjectRecord, Base):
    __tablename__ = 'project_documents'
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    __table_args__ = (UniqueConstraint('project_id', 'document_id'),)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey('documents.id'), index=True)
    notes: Mapped[str] = mapped_column(Text, default='')

class Readiness(ProjectRecord, Base):
    __tablename__ = 'project_readiness'
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    __table_args__ = (UniqueConstraint('project_id', 'category'),)
    category: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default='NOT_STARTED', index=True)
    owner: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), index=True, default=None)
    notes: Mapped[str] = mapped_column(Text, default='')

class TaskComment(ProjectRecord, Base):
    __tablename__ = 'project_comments'
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey('project_tasks.id'), index=True)
    content: Mapped[str] = mapped_column(Text)
    author_id: Mapped[int] = mapped_column(ForeignKey('users.id'))


class ProjectActivity(Base):
    __tablename__ = 'project_activity'
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(60))
    before: Mapped[dict] = mapped_column(JSON, default=dict)
    after: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)

MODELS = {'projects': Project, 'wbs': Wbs, 'tasks': Task, 'dependencies': TaskDependency, 'ecr': Ecr, 'eco': Eco, 'issues': Issue, 'risks': Risk, 'decisions': Decision, 'milestones': Milestone, 'budget': BudgetEntry, 'vendors': Vendor, 'documents': ProjectDocument, 'readiness': Readiness, 'comments': TaskComment}
