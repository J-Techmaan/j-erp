from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.core.database import Base, make_engine
from app.core.migrations import migrate_legacy_users
from app.models import AuthAccount, Document, Schedule, User


def test_legacy_sqlite_upgrade_preserves_ids_documents_and_foreign_keys(tmp_path):
    path = tmp_path / 'legacy.db'
    engine = make_engine('sqlite:///' + path.as_posix())
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        conn.exec_driver_sql('PRAGMA foreign_keys=OFF')
        conn.exec_driver_sql('DROP TABLE users')
        conn.exec_driver_sql("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY, instagram_user_id VARCHAR(100) NOT NULL UNIQUE,
                username VARCHAR(100) NOT NULL UNIQUE, display_name VARCHAR(100) NOT NULL,
                profile_image_url VARCHAR(2000), is_active BOOLEAN NOT NULL,
                created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL
            )
        """)
        conn.exec_driver_sql("""
            INSERT INTO users VALUES
            (17, 'mock-instagram-user1', 'user1', '기존 사용자', NULL, 1, '2026-09-07', '2026-09-07'),
            (23, 'old-external-subject', 'user2', '기존 외부 계정', NULL, 1, '2026-09-07', '2026-09-07')
        """)
        conn.commit()
        conn.exec_driver_sql('PRAGMA foreign_keys=ON')
    with Session(engine) as db:
        doc = Document(author_id=17, title='보존할 문서', content='원문')
        db.add(doc)
        db.commit()
        document_id = doc.id
    migrate_legacy_users(engine)
    Base.metadata.create_all(engine)
    migrate_legacy_users(engine)
    assert 'instagram_user_id' not in {c['name'] for c in inspect(engine).get_columns('users')}
    with Session(engine) as db:
        assert db.get(User, 17).display_name == '기존 사용자'
        assert db.get(User, 17).email is None
        assert db.get(Document, document_id).content == '원문'
        assert db.get(Document, document_id).author_id == 17
        accounts = db.scalars(select(AuthAccount).order_by(AuthAccount.user_id)).all()
        assert [(a.user_id, a.provider) for a in accounts] == [(17, 'mock'), (23, 'instagram')]
        assert all(a.password_hash is None for a in accounts)
        db.add(User(email='new@example.com', username='new-user', display_name='신규 회원'))
        db.commit()
    with engine.connect() as conn:
        assert conn.exec_driver_sql('PRAGMA foreign_key_check').fetchall() == []
        assert conn.exec_driver_sql('PRAGMA foreign_keys').scalar() == 1
    assert len(list(tmp_path.glob('legacy.before-local-auth-*.db'))) == 1
    engine.dispose()
