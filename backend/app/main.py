from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm.exc import StaleDataError

from app.api import attachments, auth, documents, groups, invites, schedules
from app.core.config import get_settings
from app.core.database import Base, engine
from app.core.migrations import add_group_scopes, migrate_legacy_users, upgrade_document_lifecycle
from app.services.identity import dummy_password_hash


@asynccontextmanager
async def lifespan(app):
    migrate_legacy_users(engine)
    Base.metadata.create_all(engine)
    add_group_scopes(engine)
    upgrade_document_lifecycle(engine)
    get_settings().upload_dir.mkdir(parents=True, exist_ok=True)
    dummy_password_hash()
    yield


app = FastAPI(title='J-ERP', version='0.1.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().allowed_origins, allow_methods=['GET', 'POST', 'PUT', 'DELETE'], allow_headers=['Content-Type', 'X-CSRF-Protection'], allow_credentials=True)
for router in (auth.router, groups.router, invites.router, documents.router, schedules.router, attachments.router):
    app.include_router(router, prefix='/api')


@app.middleware('http')
async def protect_cookie_requests(request: Request, call_next):
    if request.url.path.startswith('/api/') and request.method not in {'GET', 'HEAD', 'OPTIONS'}:
        # A custom header forces browser preflight, including multipart uploads.
        # Origin checking also protects against requests from untrusted subdomains.
        origins = set(get_settings().allowed_origins)
        origin = request.headers.get('origin')
        if request.headers.get('x-csrf-protection') != '1' or (origin is not None and origin not in origins):
            return JSONResponse(status_code=403, content={'detail': '허용되지 않은 요청입니다. 화면을 새로고침해 주세요.'})
    response = await call_next(request)
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    if not request.url.path.startswith('/api/auth/'):
        from fastapi.exception_handlers import request_validation_exception_handler
        return await request_validation_exception_handler(request, exc)
    labels = {'email': '이메일', 'password': '비밀번호', 'password_confirm': '비밀번호 확인',
              'name': '이름', 'remember_me': '로그인 상태 유지'}
    messages = []
    for error in exc.errors():
        field = error['loc'][-1] if error['loc'] else ''
        label = labels.get(field, '입력값')
        kind = error['type']
        if kind == 'value_error':
            message = error['msg'].removeprefix('Value error, ')
        elif kind == 'missing':
            message = f'{label} 항목을 입력해 주세요.'
        elif kind in {'string_too_short', 'string_too_long'}:
            if field == 'password' and request.url.path.endswith('/signup'):
                message = '비밀번호는 8자 이상 128자 이하로 입력해 주세요.'
            else:
                message = f'{label} 길이를 확인해 주세요.'
        else:
            message = f'{label} 형식이 올바르지 않습니다.'
        messages.append(message)
    # Never echo Pydantic input values (which may include passwords).
    return JSONResponse(status_code=422, content={'detail': ' '.join(dict.fromkeys(messages))})


@app.exception_handler(StaleDataError)
async def stale_data(request: Request, exc: StaleDataError):
    return JSONResponse(status_code=409, content={'detail': '문서가 변경되었습니다. 새로고침 후 다시 시도하세요.'})


@app.get('/api/health')
def health():
    return {'status': 'ok'}
