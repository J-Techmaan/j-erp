from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import selectinload

from app.models import ApprovalAction, ApprovalStep, Document, DocumentStatus, StepStatus


def document_query():
    return select(Document).options(selectinload(Document.author), selectinload(Document.rejector), selectinload(Document.steps).selectinload(ApprovalStep.user), selectinload(Document.attachments), selectinload(Document.history).selectinload(ApprovalAction.user))


def visible_to(user_id):
    return or_(Document.author_id == user_id, and_(Document.status != DocumentStatus.DRAFT, Document.steps.any(ApprovalStep.user_id == user_id)), Document.history.any(ApprovalAction.user_id == user_id))


def get_document(db, document_id, user_id, group_id=None):
    query = document_query().where(Document.id == document_id, visible_to(user_id))
    if group_id is not None:
        query = query.where(Document.group_id == group_id)
    doc = db.scalar(query)
    if doc is None:
        raise HTTPException(404, '문서를 찾을 수 없습니다.')
    return doc


def list_documents(db, user_id, group_id, scope, status, offset, limit):
    query = document_query().where(Document.group_id == group_id, visible_to(user_id))
    if scope == 'authored':
        query = query.where(Document.author_id == user_id)
    elif scope == 'pending':
        query = query.where(Document.status == DocumentStatus.IN_PROGRESS, Document.steps.any(and_(ApprovalStep.user_id == user_id, ApprovalStep.status == StepStatus.CURRENT)))
    elif scope == 'history':
        query = query.where(Document.history.any(and_(ApprovalAction.user_id == user_id, ApprovalAction.action.in_(['APPROVED', 'REJECTED']))))
    elif scope == 'notified':
        query = query.where(Document.status.in_([DocumentStatus.COMPLETED, DocumentStatus.REJECTED]), Document.steps.any(and_(ApprovalStep.user_id == user_id, ApprovalStep.approval_type == 'NOTIFICATION')))
    if status:
        query = query.where(Document.status == status)
    return db.scalars(query.order_by(Document.updated_at.desc(), Document.id.desc()).offset(offset).limit(limit)).all()
