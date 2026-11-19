"""
SQLAlchemy engine, session, and Base setup for the standalone SQLite database.

All models share this declarative Base. Call `init_db()` once at app
startup to create tables and seed a default admin user/roles.
"""

import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "workflow.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# check_same_thread=False because the execution engine may run on a
# background thread while the UI runs on the main thread.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

Base = declarative_base()


@contextmanager
def get_session():
    """Context-managed session: commits on success, rolls back on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """Create all tables (if they don't exist) and seed default data."""
    # Import models so they're registered on Base.metadata before create_all.
    from app.models import user, workflow, execution, notification, audit  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _seed_default_data()


def _seed_default_data():
    from app.models.user import User, Role
    from app.auth.auth_service import hash_password

    with get_session() as session:
        if session.query(Role).count() == 0:
            roles = [Role(name="Admin"), Role(name="Manager"), Role(name="Employee")]
            session.add_all(roles)
            session.flush()

        if session.query(User).filter_by(username="admin").first() is None:
            admin_role = session.query(Role).filter_by(name="Admin").first()
            admin_user = User(
                username="admin",
                full_name="Administrator",
                password_hash=hash_password("admin123"),
                role=admin_role,
            )
            session.add(admin_user)
            # TODO: remove/replace this default credential before any real use.
