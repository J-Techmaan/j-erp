from datetime import datetime, timezone

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import ApprovalType, DocumentStatus, GroupRole, MembershipStatus, StepStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator('*', mode='after')
    @classmethod
    def utc_dates(cls, value):
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class UserOut(ORMModel):
    id: int
    username: str
    display_name: str
    profile_image_url: str | None
    is_active: bool


class CurrentUserOut(UserOut):
    email: str | None


class LoginIn(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=128)
    remember_me: bool = False

    @field_validator('email')
    @classmethod
    def normalize_email(cls, value):
        from email_validator import EmailNotValidError, validate_email
        try:
            return validate_email(value.strip(), check_deliverability=False, allow_smtputf8=False).normalized.casefold()
        except EmailNotValidError:
            raise ValueError('올바른 이메일 주소를 입력해 주세요.')


class SignupIn(LoginIn):
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    password_confirm: str = Field(min_length=1, max_length=128)

    @field_validator('name')
    @classmethod
    def validate_name(cls, value):
        value = value.strip()
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError('이름을 올바르게 입력해 주세요.')
        return value

    @model_validator(mode='after')
    def validate_password(self):
        if self.password != self.password_confirm:
            raise ValueError('비밀번호가 일치하지 않습니다.')
        if not self.password.strip():
            raise ValueError('공백만으로 된 비밀번호는 사용할 수 없습니다.')
        return self


class StepIn(BaseModel):
    user_id: int = Field(gt=0)
    approval_type: ApprovalType = ApprovalType.APPROVAL


class DocumentIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(default='', max_length=100000)
    steps: list[StepIn] = Field(default_factory=list, max_length=50)

    @field_validator('title')
    @classmethod
    def title_not_blank(cls, value):
        if not value.strip():
            raise ValueError('제목을 입력하세요.')
        return value.strip()

    @model_validator(mode='after')
    def unique_users(self):
        if len({step.user_id for step in self.steps}) != len(self.steps):
            raise ValueError('결재선에 같은 사용자를 중복 추가할 수 없습니다.')
        return self


class DocumentUpdate(DocumentIn):
    revision: int = Field(gt=0)


class RevisionIn(BaseModel):
    revision: int = Field(gt=0)


class SubmitIn(RevisionIn):
    message: str = Field(default='', max_length=2000)


class ActionIn(RevisionIn):
    comment: str = Field(default='', max_length=2000)


class StepOut(ORMModel):
    id: int
    user_id: int
    user: UserOut
    step_order: int
    approval_type: ApprovalType
    status: StepStatus
    comment: str | None
    acted_at: datetime | None


class AttachmentOut(ORMModel):
    id: int
    original_filename: str
    file_size: int
    mime_type: str
    created_at: datetime


class ActionOut(ORMModel):
    id: int
    user: UserOut
    action: str
    round_number: int
    comment: str | None
    acted_at: datetime


class DocumentOut(ORMModel):
    id: int
    document_number: str
    title: str
    content: str
    author_id: int
    group_id: int | None
    author: UserOut
    status: DocumentStatus
    revision: int
    round_number: int
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None
    completed_at: datetime | None
    rejected_at: datetime | None
    cancelled_at: datetime | None
    rejector_id: int | None
    rejector: UserOut | None
    source_document_id: int | None
    steps: list[StepOut]
    attachments: list[AttachmentOut]
    history: list[ActionOut]


class ScheduleIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=10000)
    start_at: AwareDatetime
    end_at: AwareDatetime
    all_day: bool = False

    @model_validator(mode='after')
    def valid_range(self):
        self.title = self.title.strip()
        if not self.title:
            raise ValueError('일정 제목을 입력하세요.')
        self.start_at = self.start_at.astimezone(timezone.utc)
        self.end_at = self.end_at.astimezone(timezone.utc)
        if self.end_at < self.start_at:
            raise ValueError('종료일은 시작일보다 빠를 수 없습니다.')
        return self


class ScheduleOut(ORMModel):
    id: int
    user_id: int
    group_id: int | None
    title: str
    description: str
    start_at: datetime
    end_at: datetime
    all_day: bool
    created_at: datetime
    updated_at: datetime


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator('name')
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('그룹 이름을 입력해 주세요.')
        return value


class GroupJoin(BaseModel):
    code: str = Field(min_length=6, max_length=12)

    @field_validator('code')
    @classmethod
    def clean_code(cls, value):
        return value.strip().upper()


class MembershipOut(ORMModel):
    id: int
    user: UserOut
    role: GroupRole
    is_admin: bool
    status: MembershipStatus
    created_at: datetime


class GroupOut(ORMModel):
    id: int
    name: str
    code: str
    owner_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    my_role: GroupRole | None = None
    members: list[MembershipOut] = []
