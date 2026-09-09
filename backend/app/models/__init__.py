from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def now():
    return datetime.now(timezone.utc)


class DocumentStatus(str, Enum):
    DRAFT = 'DRAFT'
    IN_PROGRESS = 'IN_PROGRESS'
    COMPLETED = 'COMPLETED'
    REJECTED = 'REJECTED'
    CANCELLED = 'CANCELLED'


class ApprovalType(str, Enum):
    APPROVAL = 'APPROVAL'
    AGREEMENT = 'AGREEMENT'
    NOTIFICATION = 'NOTIFICATION'


class StepStatus(str, Enum):
    WAITING = 'WAITING'
    CURRENT = 'CURRENT'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'
    NOTIFIED = 'NOTIFIED'


class GroupRole(str, Enum):
    OWNER = 'OWNER'
    MEMBER = 'MEMBER'


class MembershipStatus(str, Enum):
    PENDING = 'PENDING'
    ACTIVE = 'ACTIVE'
    REJECTED = 'REJECTED'


def enum_column(enum):
    return SAEnum(enum, native_enum=False, create_constraint=True, validate_strings=True)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class User(Timestamps, Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str | None] = mapped_column(String(254), unique=True, default=None)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    profile_image_url: Mapped[str | None] = mapped_column(String(2000), default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AuthAccount(Base):
    __tablename__ = 'auth_accounts'
    __table_args__ = (
        UniqueConstraint('provider', 'provider_user_id'),
        UniqueConstraint('user_id', 'provider'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    provider: Mapped[str] = mapped_column(String(30))
    provider_user_id: Mapped[str] = mapped_column(String(254))
    password_hash: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    user: Mapped[User] = relationship()


class AuthSession(Base):
    __tablename__ = 'auth_sessions'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    user: Mapped[User] = relationship()


class Group(Timestamps, Base):
    __tablename__ = 'groups'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    code: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    owner: Mapped[User] = relationship()


class GroupInvite(Base):
    __tablename__ = 'group_invites'
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey('groups.id'), index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class GroupMembership(Base):
    __tablename__ = 'group_memberships'
    __table_args__ = (UniqueConstraint('group_id', 'user_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey('groups.id', ondelete='CASCADE'), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    role: Mapped[GroupRole] = mapped_column(enum_column(GroupRole), default=GroupRole.MEMBER)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[MembershipStatus] = mapped_column(enum_column(MembershipStatus), default=MembershipStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    user: Mapped[User] = relationship()
    group: Mapped[Group] = relationship()


class Document(Timestamps, Base):
    __tablename__ = 'documents'
    id: Mapped[int] = mapped_column(primary_key=True)
    document_number: Mapped[str] = mapped_column(String(60), unique=True, default=lambda: f'ERP-{now():%Y%m%d}-{uuid4().hex[:16].upper()}')
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text, default='')
    author_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey('groups.id'), index=True)
    status: Mapped[DocumentStatus] = mapped_column(enum_column(DocumentStatus), default=DocumentStatus.DRAFT, index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejector_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), index=True)
    source_document_id: Mapped[int | None] = mapped_column(ForeignKey('documents.id'), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    round_number: Mapped[int] = mapped_column(Integer, default=0)
    __mapper_args__ = {'version_id_col': revision}
    author: Mapped[User] = relationship(foreign_keys=[author_id])
    rejector: Mapped[User | None] = relationship(foreign_keys=[rejector_id])
    steps: Mapped[list['ApprovalStep']] = relationship(cascade='all, delete-orphan', order_by='ApprovalStep.step_order')
    attachments: Mapped[list['DocumentAttachment']] = relationship(cascade='all, delete-orphan')
    history: Mapped[list['ApprovalAction']] = relationship(cascade='all, delete-orphan', order_by='ApprovalAction.id')


class ApprovalStep(Base):
    __tablename__ = 'approval_steps'
    __table_args__ = (UniqueConstraint('document_id', 'step_order'), UniqueConstraint('document_id', 'user_id'))
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey('documents.id'), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    step_order: Mapped[int] = mapped_column(Integer)
    approval_type: Mapped[ApprovalType] = mapped_column(enum_column(ApprovalType))
    status: Mapped[StepStatus] = mapped_column(enum_column(StepStatus), default=StepStatus.WAITING)
    comment: Mapped[str | None] = mapped_column(Text)
    acted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship()


class ApprovalAction(Base):
    """Immutable audit records survive editing the line and resubmission."""
    __tablename__ = 'approval_actions'
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey('documents.id'), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    round_number: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(30))
    comment: Mapped[str | None] = mapped_column(Text)
    acted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    user: Mapped[User] = relationship()


class DocumentAttachment(Base):
    __tablename__ = 'document_attachments'
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey('documents.id'), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(100), unique=True)
    file_path: Mapped[str] = mapped_column(String(1000))
    file_size: Mapped[int] = mapped_column(Integer)
    mime_type: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Schedule(Timestamps, Base):
    __tablename__ = 'schedules'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey('groups.id'), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default='')
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
