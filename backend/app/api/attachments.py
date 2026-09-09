import mimetypes
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.core.security import CurrentUser, Db
from app.core.groups import CurrentMembership
from app.models import DocumentAttachment, now
from app.repositories.documents import get_document
from app.schemas import AttachmentOut
from app.services.approvals import check_revision, commit, require_draft_author

router = APIRouter(tags=['attachments'])


@router.post('/documents/{document_id}/attachments', response_model=AttachmentOut, status_code=201)
def upload(document_id: int, db: Db, user: CurrentUser, membership: CurrentMembership, revision: int = Form(gt=0), file: UploadFile = File()):
    doc = get_document(db, document_id, user.id, membership.group_id)
    require_draft_author(doc, user.id)
    check_revision(doc, revision)
    settings = get_settings()
    filename = (file.filename or '').replace('\\', '/').rsplit('/', 1)[-1]
    extension = Path(filename).suffix.lower()
    if not filename or len(filename) > 255 or any(ord(c) < 32 for c in filename) or extension not in {s.strip().lower() for s in settings.allowed_extensions.split(',')}:
        raise HTTPException(422, '허용되지 않는 파일 이름 또는 확장자입니다.')
    stored = uuid4().hex + extension
    path = settings.upload_dir / stored
    size = 0
    try:
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as output:
            while chunk := file.file.read(64 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise HTTPException(413, '첨부파일 크기 제한을 초과했습니다.')
                output.write(chunk)
        attachment = DocumentAttachment(original_filename=filename, stored_filename=stored, file_path=str(path), file_size=size, mime_type=mimetypes.guess_type(filename)[0] or 'application/octet-stream')
        doc.attachments.append(attachment)
        doc.updated_at = now()  # Version the parent alongside the attachment transaction.
        commit(db)
        return attachment
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    finally:
        file.file.close()


@router.get('/attachments/{attachment_id}/download')
def download(attachment_id: int, db: Db, user: CurrentUser, membership: CurrentMembership):
    attachment = db.get(DocumentAttachment, attachment_id)
    if attachment is None:
        raise HTTPException(404, '첨부파일을 찾을 수 없습니다.')
    get_document(db, attachment.document_id, user.id, membership.group_id)
    root = get_settings().upload_dir.resolve()
    path = (root / attachment.stored_filename).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(404, '첨부파일을 찾을 수 없습니다.')
    return FileResponse(path, filename=attachment.original_filename, media_type='application/octet-stream', headers={'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'no-store'})
