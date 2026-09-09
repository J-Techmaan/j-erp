"""One-time, transactional upgrade of the original SQLite identity schema."""
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from sqlalchemy import inspect

from app.models import AuthAccount


def migrate_legacy_users(engine):
    inspector = inspect(engine)
    if not inspector.has_table('users'):
        return
    if 'instagram_user_id' not in {c['name'] for c in inspector.get_columns('users')}:
        return
    if engine.dialect.name != 'sqlite':
        raise RuntimeError('The legacy identity upgrade requires a SQLite database.')

    with engine.connect() as conn:
        conn.commit()
        # Keep a database snapshot before altering legacy data. No file is removed.
        database = engine.url.database
        if database and database != ':memory:':
            stamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
            backup = Path(database).with_suffix(f'.before-local-auth-{stamp}.db')
            with sqlite3.connect(str(backup)) as target:
                conn.connection.driver_connection.backup(target)
        conn.exec_driver_sql('PRAGMA foreign_keys=OFF')
        conn.commit()
        try:
            conn.exec_driver_sql('BEGIN IMMEDIATE')
            # Another startup process may already have completed the upgrade.
            columns = {row[1] for row in conn.exec_driver_sql('PRAGMA table_info(users)')}
            if 'instagram_user_id' not in columns:
                conn.commit()
                return
            AuthAccount.__table__.create(conn, checkfirst=True)
            conn.exec_driver_sql("""
                INSERT INTO auth_accounts (user_id, provider, provider_user_id, created_at)
                SELECT id, CASE WHEN instagram_user_id LIKE 'mock-instagram-%'
                    THEN 'mock' ELSE 'instagram' END, instagram_user_id, created_at
                FROM users
            """)
            conn.exec_driver_sql("""
                CREATE TABLE users_local_upgrade (
                    id INTEGER NOT NULL PRIMARY KEY,
                    email VARCHAR(254) UNIQUE,
                    username VARCHAR(100) NOT NULL UNIQUE,
                    display_name VARCHAR(100) NOT NULL,
                    profile_image_url VARCHAR(2000),
                    is_active BOOLEAN NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
            """)
            conn.exec_driver_sql("""
                INSERT INTO users_local_upgrade
                    (id, username, display_name, profile_image_url, is_active, created_at, updated_at)
                SELECT id, username, display_name, profile_image_url, is_active, created_at, updated_at
                FROM users
            """)
            conn.exec_driver_sql('DROP TABLE users')
            conn.exec_driver_sql('ALTER TABLE users_local_upgrade RENAME TO users')
            if conn.exec_driver_sql('PRAGMA foreign_key_check').fetchall():
                raise RuntimeError('Identity migration failed foreign key validation.')
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.exec_driver_sql('PRAGMA foreign_keys=ON')
            conn.commit()


def add_group_scopes(engine):
    """Add nullable group scopes to existing SQLite business tables."""
    if engine.dialect.name != 'sqlite':
        return
    with engine.begin() as conn:
        membership_columns = {row[1] for row in conn.exec_driver_sql('PRAGMA table_info(group_memberships)')}
        if 'is_admin' not in membership_columns:
            conn.exec_driver_sql('ALTER TABLE group_memberships ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0')
        group_columns = {row[1] for row in conn.exec_driver_sql('PRAGMA table_info(groups)')}
        if 'is_active' not in group_columns:
            conn.exec_driver_sql('ALTER TABLE groups ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1')
        for table in ('documents', 'schedules'):
            columns = {row[1] for row in conn.exec_driver_sql(f'PRAGMA table_info({table})')}
            if 'group_id' not in columns:
                conn.exec_driver_sql(f'ALTER TABLE {table} ADD COLUMN group_id INTEGER REFERENCES groups(id)')
            conn.exec_driver_sql(f'CREATE INDEX IF NOT EXISTS ix_{table}_group_id ON {table} (group_id)')


def upgrade_document_lifecycle(engine):
    """Add terminal lifecycle metadata and expand the SQLite status constraint."""
    if engine.dialect.name != 'sqlite' or not inspect(engine).has_table('documents'):
        return
    with engine.connect() as conn:
        sql = conn.exec_driver_sql("SELECT sql FROM sqlite_master WHERE type='table' AND name='documents'").scalar() or ''
        columns = {row[1] for row in conn.exec_driver_sql('PRAGMA table_info(documents)')}
        if {'rejected_at', 'cancelled_at', 'rejector_id', 'source_document_id'} <= columns and "'CANCELLED'" in sql:
            return
        conn.commit()
        conn.exec_driver_sql('PRAGMA foreign_keys=OFF')
        try:
            conn.exec_driver_sql('BEGIN IMMEDIATE')
            conn.exec_driver_sql('''
                CREATE TABLE documents_lifecycle_upgrade (
                    id INTEGER NOT NULL PRIMARY KEY,
                    document_number VARCHAR(60) NOT NULL UNIQUE,
                    title VARCHAR(200) NOT NULL,
                    content TEXT NOT NULL,
                    author_id INTEGER NOT NULL REFERENCES users(id),
                    group_id INTEGER REFERENCES groups(id),
                    status VARCHAR(11) NOT NULL CHECK (status IN ('DRAFT','IN_PROGRESS','COMPLETED','REJECTED','CANCELLED')),
                    submitted_at DATETIME,
                    completed_at DATETIME,
                    rejected_at DATETIME,
                    cancelled_at DATETIME,
                    rejector_id INTEGER REFERENCES users(id),
                    source_document_id INTEGER REFERENCES documents(id),
                    revision INTEGER NOT NULL,
                    round_number INTEGER NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
            ''')
            rejected_at = 'rejected_at' if 'rejected_at' in columns else 'NULL'
            cancelled_at = 'cancelled_at' if 'cancelled_at' in columns else 'NULL'
            rejector_id = 'rejector_id' if 'rejector_id' in columns else 'NULL'
            source_document_id = 'source_document_id' if 'source_document_id' in columns else 'NULL'
            conn.exec_driver_sql(f'''
                INSERT INTO documents_lifecycle_upgrade
                    (id, document_number, title, content, author_id, group_id, status, submitted_at,
                     completed_at, rejected_at, cancelled_at, rejector_id, source_document_id,
                     revision, round_number, created_at, updated_at)
                SELECT id, document_number, title, content, author_id, group_id, status, submitted_at,
                       completed_at, {rejected_at}, {cancelled_at}, {rejector_id}, {source_document_id},
                       revision, round_number, created_at, updated_at FROM documents
            ''')
            conn.exec_driver_sql('DROP TABLE documents')
            conn.exec_driver_sql('ALTER TABLE documents_lifecycle_upgrade RENAME TO documents')
            for column in ('author_id', 'group_id', 'status', 'rejector_id', 'source_document_id'):
                conn.exec_driver_sql(f'CREATE INDEX ix_documents_{column} ON documents ({column})')
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.exec_driver_sql('PRAGMA foreign_keys=ON')
            conn.commit()
