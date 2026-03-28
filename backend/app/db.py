from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from backend.app.config import settings


Base = declarative_base()

engine_kwargs = {
    "echo": settings.debug,
}

if settings.database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs.update(
        {
            "pool_size": 10,
            "max_overflow": 20,
            "pool_pre_ping": True,
            "pool_recycle": 3600,
        }
    )

engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


REQUIRED_TABLES = frozenset(
    {
        "balances",
        "loyalty_tier_rules",
        "ml_models",
        "payments",
        "predictions",
        "transactions",
        "users",
    }
)


def database_connection_ok(db: Session) -> bool:
    db.execute(text("SELECT 1"))
    return True


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _missing_tables(table_names: Iterable[str]) -> list[str]:
    existing = set(table_names)
    return sorted(REQUIRED_TABLES - existing)


def database_schema_status(db: Session) -> tuple[bool, str, list[str]]:
    try:
        inspector = inspect(db.bind)
        missing_tables = _missing_tables(inspector.get_table_names())
    except SQLAlchemyError as exc:
        return False, f"schema_probe_failed:{exc.__class__.__name__}", []

    if missing_tables:
        return False, "missing_tables", missing_tables
    return True, "ok", []


def probe_database_health(session_factory=None) -> tuple[str, str, list[str]]:
    db_status = "unknown"
    schema_status = "unknown"
    missing_tables: list[str] = []
    db: Session | None = None
    try:
        if session_factory is None:
            session_factory = SessionLocal
        db = session_factory()
        database_connection_ok(db)
        db_status = "ok"
        _, schema_status, missing_tables = database_schema_status(db)
    except Exception:
        db_status = "error"
        schema_status = "unknown"
    finally:
        if db is not None:
            db.close()
    return db_status, schema_status, missing_tables


import backend.app.models  # noqa: F401,E402
