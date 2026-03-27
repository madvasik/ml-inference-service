from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


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


def schema_is_ready(db: Session) -> bool:
    ready, _, _ = database_schema_status(db)
    return ready
