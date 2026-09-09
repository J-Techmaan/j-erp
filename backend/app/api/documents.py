from typing import Literal

from fastapi import APIRouter, Query

from app.core.security import CurrentUser, Db
from app.core.groups import CurrentMembership
from app.models import ApprovalStep, Document, DocumentStatus
from app.repositories.documents import get_document, list_documents
from app.schemas import ActionIn, DocumentIn, DocumentOut, DocumentUpdate, RevisionIn, SubmitIn
from app.services import approvals

router = APIRouter(tags=['documents / approvals'])


@router.post('/documents', response_model=DocumentOut, status_code=201)
def create_document(data: DocumentIn, db: Db, user: CurrentUser, membership: CurrentMembership):
    doc = Document(author_id=user.id, group_id=membership.group_id, title=data.title, content=data.content)
    db.add(doc)
    approvals.set_content(db, doc, data)
    approvals.commit(db)
    return doc


@router.get('/documents', response_model=list[DocumentOut])
def documents(db: Db, user: CurrentUser, membership: CurrentMembership, scope: Literal['all', 'group', 'authored', 'pending', 'history', 'notified'] = 'all', status: DocumentStatus | None = None, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    return list_documents(db, user.id, membership.group_id, scope, status, offset, limit)


@router.get('/documents/{document_id}', response_model=DocumentOut)
def detail(document_id: int, db: Db, user: CurrentUser, membership: CurrentMembership):
    return get_document(db, document_id, user.id, membership.group_id)


@router.put('/documents/{document_id}', response_model=DocumentOut)
def update_document(document_id: int, data: DocumentUpdate, db: Db, user: CurrentUser, membership: CurrentMembership):
    doc = get_document(db, document_id, user.id, membership.group_id)
    approvals.require_draft_author(doc, user.id)
    approvals.check_revision(doc, data.revision)
    approvals.set_content(db, doc, data)
    approvals.commit(db)
    return doc


@router.post('/documents/{document_id}/submit', response_model=DocumentOut)
def submit(document_id: int, data: SubmitIn, db: Db, user: CurrentUser, membership: CurrentMembership):
    doc = get_document(db, document_id, user.id, membership.group_id)
    approvals.submit(db, doc, user.id, data.revision, data.message)
    return doc


@router.post('/documents/{document_id}/recreate', response_model=DocumentOut, status_code=201)
def recreate(document_id: int, db: Db, user: CurrentUser, membership: CurrentMembership):
    source = get_document(db, document_id, user.id, membership.group_id)
    if source.author_id != user.id:
        from fastapi import HTTPException
        raise HTTPException(403, '작성자만 문서를 재작성할 수 있습니다.')
    if source.status not in {DocumentStatus.REJECTED, DocumentStatus.CANCELLED}:
        from fastapi import HTTPException
        raise HTTPException(409, '반려되거나 취소된 문서만 재작성할 수 있습니다.')
    doc = Document(author_id=user.id, group_id=source.group_id, title=source.title, content=source.content, source_document_id=source.id)
    doc.steps = [ApprovalStep(user_id=s.user_id, step_order=s.step_order, approval_type=s.approval_type) for s in source.steps]
    db.add(doc)
    approvals.commit(db)
    return doc


@router.post('/documents/{document_id}/approve', response_model=DocumentOut)
def approve(document_id: int, data: ActionIn, db: Db, user: CurrentUser, membership: CurrentMembership):
    doc = get_document(db, document_id, user.id, membership.group_id)
    approvals.act(db, doc, user.id, data)
    return doc


@router.post('/documents/{document_id}/reject', response_model=DocumentOut)
def reject(document_id: int, data: ActionIn, db: Db, user: CurrentUser, membership: CurrentMembership):
    doc = get_document(db, document_id, user.id, membership.group_id)
    approvals.act(db, doc, user.id, data, reject=True)
    return doc


@router.post('/documents/{document_id}/cancel', response_model=DocumentOut)
def cancel(document_id: int, data: RevisionIn, db: Db, user: CurrentUser, membership: CurrentMembership):
    doc = get_document(db, document_id, user.id, membership.group_id)
    approvals.cancel(db, doc, user.id, data.revision)
    return doc


@router.get('/approvals/pending', response_model=list[DocumentOut])
def pending(db: Db, user: CurrentUser, membership: CurrentMembership, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    return list_documents(db, user.id, membership.group_id, 'pending', None, offset, limit)


@router.get('/approvals/history', response_model=list[DocumentOut])
def history(db: Db, user: CurrentUser, membership: CurrentMembership, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    return list_documents(db, user.id, membership.group_id, 'history', None, offset, limit)
