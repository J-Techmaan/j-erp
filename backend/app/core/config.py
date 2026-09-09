from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / '.env', extra='ignore')
    app_env: str = 'development'
    session_cookie_secure: bool = False
    session_hours: int = Field(default=8, ge=1, le=168)
    persistent_session_days: int = Field(default=30, ge=1, le=90)
    database_url: str = 'sqlite:///./erp.db'
    upload_dir: Path = BACKEND_DIR / 'uploads'
    max_upload_bytes: int = 10 * 1024 * 1024
    allowed_extensions: str = '.txt,.pdf,.png,.jpg,.jpeg,.csv,.xlsx,.docx'
    cors_origins: str = 'http://localhost:5173,http://127.0.0.1:5173'
    public_origin: str = ''

    @property
    def allowed_origins(self):
        return [value.strip().rstrip('/') for value in f'{self.cors_origins},{self.public_origin}'.split(',') if value.strip()]

    @model_validator(mode='after')
    def validate_config(self):
        if self.app_env != 'development' and not self.session_cookie_secure:
            raise ValueError('SESSION_COOKIE_SECURE=true and HTTPS are required outside development.')
        if self.max_upload_bytes <= 0:
            raise ValueError('Upload size must be positive.')
        if not self.upload_dir.is_absolute():
            self.upload_dir = BACKEND_DIR / self.upload_dir
        if self.database_url.startswith('sqlite:///./'):
            self.database_url = 'sqlite:///' + (BACKEND_DIR / self.database_url[12:]).as_posix()
        if any('*' in origin for origin in self.allowed_origins):
            raise ValueError('Explicit CORS origins are required for cookie authentication.')
        return self


@lru_cache
def get_settings():
    return Settings()
