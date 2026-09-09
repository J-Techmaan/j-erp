# J-ERP · 전자결재 및 개인 일정 MVP

Vue 3 프론트엔드와 FastAPI 백엔드로 구성한 사내 업무 시스템입니다. 메모 문서를 작성하고 결재선을 지정하면 결재·합의가 순서대로 진행됩니다. 마지막 승인 후 완결되며 통보 대상에게 완결 문서가 표시됩니다.

외부에서 접속할 때는 공유기에서 프론트엔드 포트를 전달하고 `backend/.env`의 `PUBLIC_ORIGIN`에 실제 접속 주소를 정확히 지정합니다(예: `http://203.0.113.10:5173`). 변경 후 두 서버를 다시 시작해야 하며 HTTPS 운영 시 `SESSION_COOKIE_SECURE=true`를 설정합니다.

## 구현 기능

- 이메일·비밀번호 회원가입/로그인, Argon2id 해시, HttpOnly 쿠키 세션, 로그인 상태 유지
- 문서 작성·임시저장·수정·목록·상태 필터·페이지 이동
- 사용자 검색, 결재/합의/통보 지정, 위·아래 순서 변경
- 상신, 순차 승인, 반려 종료, 원본을 보존하는 새 문서 재작성
- 문서 버전 검증과 DB 트랜잭션으로 중복·동시 처리 방지
- 승인 이력과 반려 사유 영구 기록, 통보 완료 목록
- 권한을 확인하는 첨부 업로드·다운로드, 확장자 및 크기 제한
- 개인 일정 추가·수정·삭제, 월간 달력, 월 이동, 종일 일정
- 대시보드의 현재 결재 대기 목록과 최근 작성 문서

실제 Instagram OAuth, 외부 알림, 조직도, 회계, 전자서명, Docker 배포는 이번 MVP 범위에 포함하지 않습니다. 기존 Mock 로그인 경로는 제거했으며 외부 계정 연동은 아직 구현하지 않았습니다.

## 기술 및 폴더 구조

Python 3.12+, FastAPI, SQLAlchemy 2, Pydantic 2, SQLite, argon2-cffi, email-validator / Vue 3, Vite, TypeScript, Vue Router, Pinia, Axios / pytest, Playwright.

```text
J-ERP/
├── app.py                    # 프로젝트 루트에서 백엔드 실행
├── start-backend.ps1
├── start-frontend.ps1
├── backend/
│   ├── app/
│   │   ├── api/              # 인증·문서·결재·일정·첨부 API
│   │   ├── core/             # 환경설정·DB 전환·세션
│   │   ├── models/           # SQLAlchemy 데이터 모델
│   │   ├── schemas/          # 요청 및 응답 검증
│   │   ├── repositories/     # 문서 조회 및 열람 범위
│   │   ├── services/         # 결재 상태 전이·비밀번호 검증
│   │   └── main.py
│   ├── tests/
│   ├── uploads/              # 비공개 첨부 저장소
│   ├── .env.example
│   ├── requirements.txt      # 호환 버전 범위
│   └── requirements.lock.txt # 실제 검증한 환경의 고정 버전
└── frontend/
    ├── src/{api,components,router,stores,types,views}/
    ├── tests/                # 브라우저 업무 시나리오
    ├── package-lock.json
    └── playwright.config.ts
```

## 현재 PC에서 바로 실행

`D:\J-ERP`에 Python 가상환경과 프로젝트 전용 Node.js를 준비했습니다. 시스템 PATH는 변경하지 않았습니다. PowerShell 터미널 두 개에서 각각 실행합니다.

```powershell
# 터미널 1
cd D:\J-ERP
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-backend.ps1
```

```powershell
# 터미널 2
cd D:\J-ERP
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-frontend.ps1
```

화면: <http://127.0.0.1:5173> · API 문서: <http://127.0.0.1:8000/docs> · 상태 확인: <http://127.0.0.1:8000/api/health>

`ExecutionPolicy Bypass`는 해당 스크립트 실행 프로세스에만 적용합니다. 시스템 정책을 영구 변경하지 않습니다. 이미 스크립트 실행이 허용된 환경이면 `./start-backend.ps1`, `./start-frontend.ps1`로 실행할 수 있습니다.

## 새 환경 설치

Python 3.12 이상과 Node.js 22.12 이상을 설치합니다. Vite의 런타임 조건은 [공식 시작 문서](https://vite.dev/guide/)를 참고하세요.

```powershell
cd D:\J-ERP
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock.txt
Copy-Item backend\.env.example backend\.env
```

개발 환경에서는 기본 `.env.example` 설정으로 실행할 수 있습니다. 운영 환경은 HTTPS와 `SESSION_COOKIE_SECURE=true`, 정확한 `CORS_ORIGINS` 설정이 필요합니다. `.env`는 Git에서 제외됩니다. 이전 `JWT_SECRET` 설정은 더 이상 사용하지 않습니다.

```powershell
cd frontend
npm ci
```

가상환경을 활성화하고 백엔드 디렉터리에서 실행하는 표준 명령:

```powershell
cd D:\J-ERP
.\.venv\Scripts\Activate.ps1
cd backend
uvicorn app.main:app --reload
```

Uvicorn은 `모듈:객체` 형식을 사용하므로 요청서의 `uvicorn app.main --reload`에는 `:app`을 붙여야 합니다. 활성화 스크립트가 막힌 경우 `..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload`로 실행하세요.

프론트엔드는 `frontend`에서 `npm run dev`로 실행합니다. Node가 프로젝트 전용 설치인 현재 PC에서는 `start-frontend.ps1`이 실행에 필요한 PATH를 해당 터미널에만 설정합니다.

## 환경변수

| 변수 | 기본값 / 설명 |
| --- | --- |
| `APP_ENV` | `development` |
| `SESSION_COOKIE_SECURE` | 개발 `false`, 운영 HTTPS에서 반드시 `true` |
| `SESSION_HOURS` | `8`, 일반 로그인 서버 세션 만료 시간 |
| `PERSISTENT_SESSION_DAYS` | `30`, 로그인 상태 유지 선택 시 만료 일수 |
| `DATABASE_URL` | `sqlite:///./erp.db`, 상대경로는 backend 기준 |
| `UPLOAD_DIR` | `./uploads`, 상대경로는 backend 기준 |
| `MAX_UPLOAD_BYTES` | `10485760` (10 MiB), 파일 한 개 기준 |
| `ALLOWED_EXTENSIONS` | `.txt,.pdf,.png,.jpg,.jpeg,.csv,.xlsx,.docx` |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` |
| `VITE_API_BASE_URL` | 프론트 `.env`에 설정, 기본 `/api` |
| `API_PROXY_TARGET` | Vite 프로세스 환경변수, 기본 `http://127.0.0.1:8000` |

브라우저는 같은 출처의 `/api`로 요청하고 Vite가 백엔드로 프록시합니다. 세션 식별자는 HttpOnly·SameSite=Lax 쿠키에만 저장하고 DB에는 SHA-256 해시만 저장합니다. 일반 로그인은 브라우저 세션 쿠키와 8시간 서버 만료, 로그인 상태 유지는 30일 만료를 사용합니다. 브라우저의 세션 복구 설정에 따라 일반 쿠키도 복구될 수 있으나 서버 만료는 항상 적용됩니다. 로그아웃 시 DB 세션을 삭제하여 기존 쿠키 재사용을 차단합니다. Axios는 credentials와 `X-CSRF-Protection: 1` 헤더를 전송하며 서버는 모든 변경 요청에서 이 헤더와 허용 Origin을 확인합니다. API를 직접 호출할 때도 변경 요청에 이 헤더가 필요합니다. 새로고침과 창 포커스 복귀 시 사용자 인증을 확인합니다.

## 데이터 모델과 결재 규칙

`users`에는 고유 이메일, 기존 `username` 식별자, `display_name` 이름과 사용자 상태를 저장합니다. 비밀번호와 외부 식별자는 `auth_accounts`로 분리합니다. `(provider, provider_user_id)`와 `(user_id, provider)`는 고유하며 로컬 계정은 `provider=local`, 정규화된 이메일 및 Argon2id 해시를 사용합니다. 향후 로그인한 사용자의 재인증과 검증된 OAuth 콜백을 거쳐 같은 `user_id`에 외부 계정을 연결할 수 있습니다. 이메일 일치만으로 자동 연결하지 않습니다. `auth_sessions`는 공급자와 독립적인 만료·폐기 가능한 세션을 저장합니다. OAuth, 이메일 소유 확인, 비밀번호 재설정은 이번 구현 범위에 포함하지 않습니다.

`Document`는 작성자, 내용, 문서번호, 상태, 일시, 버전과 상신 차수를 갖습니다. `ApprovalStep`은 문서별 순서·사용자·결재 유형·현재 상태를 저장합니다. `ApprovalAction`은 각 상신 차수의 승인·반려·통보 기록을 남기므로 결재선 수정과 재상신으로 이전 사유가 사라지지 않습니다. `DocumentAttachment`는 문서에, `Schedule`은 소유 사용자에 연결됩니다.

```text
DRAFT → 상신 → IN_PROGRESS → 현재 결재자 승인 → 다음 결재자
                                     └ 마지막 승인 → COMPLETED
                                     └ 반려 → DRAFT → 수정·재상신
```

- 작성자만 기안 수정·첨부·상신 가능. 상신 후 내용과 결재선은 고정됩니다.
- 결재 또는 합의 대상이 최소 한 명 필요합니다. 빈 결재선과 통보만 있는 문서는 임시저장 가능하나 상신 불가입니다.
- 동일 사용자의 중복 결재선은 거부합니다. 자기 결재는 요구사항에 제한이 없어 허용합니다.
- `IN_PROGRESS` 문서의 `CURRENT` 사용자만 승인·반려할 수 있습니다.
- 통보는 위치와 관계없이 승인 순서에서 건너뛰고, 최종 승인 트랜잭션에서 `NOTIFIED`를 기록합니다.
- 반려 사유는 필수입니다. 반려 시 DRAFT로 돌아가고 이전 결재 상태는 화면에 남습니다. 재상신 시 단계 상태를 초기화하고 상신 차수를 늘립니다.
- 문서 수정·상신·승인·반려·첨부 요청에는 읽은 `revision`이 필요합니다. 오래된 버전과 동시 갱신 충돌은 409로 거부하며 전체 트랜잭션을 롤백합니다. SQLAlchemy의 [버전 카운터](https://docs.sqlalchemy.org/en/20/orm/versioning.html)를 사용합니다.
- 최초 기안은 작성자만 열람합니다. 상신 후 결재선 참여자도 열람할 수 있고, 과거 처리 이력에 있는 사용자는 이력 확인을 위해 열람할 수 있습니다. 관계없는 사용자에게는 404를 반환합니다.
- 첨부 저장소는 정적 공개 경로가 아닙니다. 다운로드마다 문서 열람 권한을 검사하고 실행되지 않도록 다운로드 응답으로 전달합니다. 파일 내용의 악성코드 검사는 MVP 범위에 포함하지 않습니다.
- 일정은 소유자만 조회·수정·삭제할 수 있습니다. API 입력에 시간대를 요구하고 UTC로 저장하며 브라우저의 현지 시간으로 표시합니다. 종일 일정의 종료는 마지막 날 23:59입니다.

SQLite로 검증했습니다. DB 연결은 환경변수와 SQLAlchemy 계층으로 분리했으나 PostgreSQL 드라이버 설치, 마이그레이션 및 해당 DB에서의 통합 검증은 향후 작업입니다. 개발 초기 스키마는 `create_all`로 생성하며 기존 테이블을 자동 마이그레이션하지 않습니다.

## DB 초기화와 백업

첫 시작 시 테이블을 생성합니다. 기존 SQLite DB에 `users.instagram_user_id`가 있으면 `*.before-local-auth-*.db` 백업을 만든 뒤 트랜잭션으로 사용자 ID와 기존 문서 관계를 보존하며 새 인증 구조로 전환합니다. 외부 식별자는 `auth_accounts`로 옮기고 Mock 사용자의 이메일은 비워 둡니다. 기존 Mock 계정에 공통 비밀번호를 부여하지 않으며 Mock 로그인도 허용하지 않습니다. 신규 사용자는 회원가입 화면에서 생성하세요. 기존 Mock 문서 데이터는 보존되지만 해당 계정의 로컬 인증 연결은 별도의 관리자 확인 절차가 필요합니다.

개발 데이터를 초기화하려면 백엔드를 종료하고 `backend/erp.db`와 `backend/uploads`를 프로젝트 밖의 백업 폴더에 **복사하여 보관한 뒤**, 기존 DB 파일을 다른 이름으로 바꾸고 서버를 재시작하세요. 빈 DB가 생성되며 사용자는 회원가입으로 등록합니다. 기존 uploads 파일은 새 DB에 자동 연결되지 않으므로 백업과 함께 관리합니다. 세션은 DB에 보관되므로 서버 재시작만으로 로그아웃되지 않습니다.

## 회원가입 및 로그인 사용 시나리오

각 사용자가 본인의 이메일, 이름, 12~128자 비밀번호로 회원가입합니다. 비밀번호 확인을 검증하며 이메일 중복을 거부합니다. 예시 결재를 재현하려면 아래 이름으로 각각 계정을 생성하세요. 테스트 계정은 자동 생성되지 않습니다.

1. 홍길동으로 로그인 → 새 결재 작성 → 제목·내용·첨부 입력.
2. 사용자 검색에서 김철수 `결재`, 박영희 `합의`, 최민수 `통보` 추가.
3. 필요하면 위·아래로 순서 조정 → 상신 → `상신중` 확인.
4. 로그아웃 후 김철수 로그인 → 대시보드 결재 대기 문서 → 승인.
5. 박영희로 로그인 → 결재 대기 → 승인 → `완결` 확인.
6. 최민수 로그인 → 통보 문서에서 같은 완결 문서 확인.
7. 반려는 사유 입력 후 처리하고 홍길동이 작성 문서에서 수정·재상신합니다.

## 테스트

```powershell
cd D:\J-ERP\backend
..\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
npm run build
npm run test:e2e
```

현재 PC에서 npm을 직접 실행하려면 먼저 해당 터미널에서 아래 PATH를 설정하거나 `start-frontend.ps1`과 같은 방식으로 프로젝트 전용 Node 경로를 찾으세요.

```powershell
$nodeDir = Get-ChildItem D:\J-ERP\.tools -Directory -Filter 'node-*-win-x64' | Select-Object -First 1
$env:PATH = $nodeDir.FullName + ';' + $env:PATH
```

백엔드 테스트는 문서 생성·임시저장·순차 승인·합의·최종 완결·비결재자 거부·중복 승인·동시 요청·반려·재상신·통보·첨부 권한·파일 제한·일정 격리를 검증합니다. 개발 DB 대신 별도 임시 DB를 사용합니다.

Playwright는 설치된 Edge(`msedge`)를 사용하며 8001/5174 포트에서 별도 테스트 서버와 임시 DB를 실행합니다. 개발 DB와 첨부에는 접근하지 않습니다. Edge가 없는 환경에서는 `npx playwright install chromium` 후 `PLAYWRIGHT_CHANNEL=chromium`을 설정하세요. 결과 스크린샷과 실패 시 trace는 `frontend/test-results`에 저장됩니다. 1024×768 화면에서 가로 넘침도 검사합니다.

브라우저 시나리오: 첨부 포함 순차 승인·합의·통보, 임시저장·반려·재상신, 일정 추가·수정·삭제·사용자 격리.

## 주요 API

| 메서드·경로 | 용도 |
| --- | --- |
| `POST /api/auth/signup` | `name`, `email`, `password`, `password_confirm`로 가입 및 세션 시작 |
| `POST /api/auth/login` | `email`, `password`, 선택 `remember_me`로 로그인 |
| `POST /api/auth/logout` | 현재 세션 폐기와 쿠키 삭제 |
| `GET /api/auth/me` | 현재 사용자와 본인 이메일 조회 |
| `GET /api/users/me`, `/api/users/search?q=` | 사용자 조회·검색 |
| `POST /api/documents` | 문서 생성, `steps` 배열 순서가 결재 순서 |
| `GET /api/documents?scope=authored` | all/authored/pending/history/notified, status/offset/limit 필터 |
| `GET/PUT /api/documents/{id}` | 문서 상세·기안 수정 |
| `POST /api/documents/{id}/submit` | `{ "revision": 1 }` |
| `POST /api/documents/{id}/approve`, `/reject` | `{ "revision": 2, "comment": "확인" }` |
| `GET /api/approvals/pending`, `/history` | 대기·승인 이력 |
| `POST /api/documents/{id}/attachments` | multipart `file`, `revision` |
| `GET /api/attachments/{id}/download` | 권한 검사 후 파일 다운로드 |
| `GET /api/schedules?start=...&end=...` | 기간과 겹치는 개인 일정 |
| `POST /api/schedules`, `PUT/DELETE /api/schedules/{id}` | 일정 생성·수정·삭제 |

요청·응답 스키마와 직접 호출은 실행 중인 `/docs`에서 확인할 수 있습니다. 인증 구현은 [Argon2 공식 문서](https://argon2-cffi.readthedocs.io/en/stable/)와 [OWASP 세션 관리 지침](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)을 참고했습니다.
