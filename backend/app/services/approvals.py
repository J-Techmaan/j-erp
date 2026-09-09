from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm.exc import StaleDataError

from app.models import ApprovalAction, ApprovalStep, ApprovalType, Document, DocumentStatus, GroupMembership, MembershipStatus, StepStatus, User, now


def commit(db):
    try:
        db.commit()
    except StaleDataError:
        db.rollback()
        raise HTTPException(409, '다른 요청에서 문서가 변경되었습니다. 새로고침 후 다시 시도하세요.')


def check_revision(doc, revision):
    if doc.revision != revision:
        raise HTTPException(409, '문서가 변경되었습니다. 새로고침 후 다시 시도하세요.')


def require_draft_author(doc, user_id):
    if doc.author_id != user_id:
        raise HTTPException(403, '작성자만 수정하거나 상신할 수 있습니다.')
    if doc.status != DocumentStatus.DRAFT:
        raise HTTPException(409, '기안 상태의 문서만 변경할 수 있습니다.')


def validate_line(db, steps, group_id):
    ids = {step.user_id for step in steps}
    active = set(db.scalars(select(User.id).where(User.id.in_(ids), User.is_active.is_(True))))
    if ids != active:
        raise HTTPException(422, '결재선에 존재하지 않거나 비활성인 사용자가 있습니다.')
    group_users = set(db.scalars(select(GroupMembership.user_id).where(
        GroupMembership.group_id == group_id,
        GroupMembership.user_id.in_(ids),
        GroupMembership.status == MembershipStatus.ACTIVE,
    )))
    if ids != group_users:
        raise HTTPException(422, '같은 그룹의 구성원만 결재선에 추가할 수 있습니다.')


def set_content(db, doc, data):
    validate_line(db, data.steps, doc.group_id)
    doc.title, doc.content = data.title, data.content
    # Flush deletions before inserting the reordered line to satisfy unique constraints.
    doc.steps.clear()
    doc.updated_at = now()
    db.flush()
    doc.steps = [ApprovalStep(user_id=s.user_id, step_order=i + 1, approval_type=s.approval_type) for i, s in enumerate(data.steps)]


def record(doc, user_id, action, comment=None):
    doc.history.append(ApprovalAction(user_id=user_id, round_number=doc.round_number, action=action, comment=comment))


def advance(doc):
    remaining = [s for s in doc.steps if s.approval_type != ApprovalType.NOTIFICATION and s.status == StepStatus.WAITING]
    if remaining:
        remaining[0].status = StepStatus.CURRENT
    else:
        doc.status = DocumentStatus.COMPLETED
        doc.completed_at = now()
        for step in doc.steps:
            if step.approval_type == ApprovalType.NOTIFICATION:
                step.status, step.acted_at = StepStatus.NOTIFIED, doc.completed_at
                record(doc, step.user_id, 'NOTIFIED')
    doc.updated_at = now()


def submit(db, doc, user_id, revision, message=''):
    require_draft_author(doc, user_id)
    check_revision(doc, revision)
    validate_line(db, doc.steps, doc.group_id)
    if not any(s.approval_type != ApprovalType.NOTIFICATION for s in doc.steps):
        raise HTTPException(422, '결재 또는 합의 대상이 최소 한 명 필요합니다.')
    doc.round_number += 1
    doc.status, doc.submitted_at, doc.completed_at = DocumentStatus.IN_PROGRESS, now(), None
    doc.rejected_at, doc.rejector_id = None, None
    for step in doc.steps:
        step.status, step.comment, step.acted_at = StepStatus.WAITING, None, None
    record(doc, user_id, 'SUBMITTED', message.strip() or None)
    advance(doc)
    commit(db)


def act(db, doc, user_id, data, reject=False):
    check_revision(doc, data.revision)
    if doc.status != DocumentStatus.IN_PROGRESS:
        raise HTTPException(409, '상신중인 문서만 결재할 수 있습니다.')
    current = next((s for s in doc.steps if s.status == StepStatus.CURRENT), None)
    if current is None or current.user_id != user_id or current.approval_type == ApprovalType.NOTIFICATION:
        raise HTTPException(403, '현재 결재자만 처리할 수 있습니다.')
    if reject and not data.comment.strip():
        raise HTTPException(422, '반려 사유를 입력하세요.')
    current.status = StepStatus.REJECTED if reject else StepStatus.APPROVED
    current.comment, current.acted_at = data.comment.strip() or None, now()
    record(doc, user_id, current.status.value, current.comment)
    if reject:
        doc.status = DocumentStatus.REJECTED
        doc.rejected_at = current.acted_at
        doc.rejector_id = user_id
        doc.completed_at = None
        for step in doc.steps:
            if step.approval_type == ApprovalType.NOTIFICATION:
                step.status, step.acted_at = StepStatus.NOTIFIED, current.acted_at
                record(doc, step.user_id, 'NOTIFIED')
        doc.updated_at = now()
    else:
        advance(doc)
    commit(db)


def cancel(db, doc, user_id, revision):
    check_revision(doc, revision)
    if doc.author_id != user_id:
        raise HTTPException(403, '작성자만 상신을 취소할 수 있습니다.')
    if doc.status != DocumentStatus.IN_PROGRESS:
        raise HTTPException(409, '상신중인 문서만 취소할 수 있습니다.')
    doc.status = DocumentStatus.CANCELLED
    doc.cancelled_at = now()
    doc.updated_at = doc.cancelled_at
    record(doc, user_id, 'CANCELLED')
    commit(db)
