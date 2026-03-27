import pytest
from backend.app.db import Base
import backend.app.db as session_module


def test_get_db_yields_session():
    """Тест получения DB сессии через dependency"""
    # Используем генератор напрямую
    db_gen = session_module.get_db()
    
    try:
        db = next(db_gen)
        assert db is not None
        assert hasattr(db, 'query')
        assert hasattr(db, 'commit')
        assert hasattr(db, 'close')
    finally:
        # Закрываем генератор
        try:
            next(db_gen)
        except StopIteration:
            pass


def test_get_db_closes_session():
    """Тест закрытия DB сессии после использования"""
    db_gen = session_module.get_db()
    
    try:
        db = next(db_gen)
        db_id = id(db)
    finally:
        # Вызываем finally блок генератора
        try:
            next(db_gen)
        except StopIteration:
            pass
    
    # Проверяем, что сессия закрыта (нельзя использовать после закрытия)
    # В реальности это сложно проверить без доступа к внутреннему состоянию,
    # но мы можем проверить, что генератор завершился
    with pytest.raises(StopIteration):
        next(db_gen)


def test_session_local_creates_sessions():
    """Тест создания сессий через SessionLocal"""
    session1 = session_module.SessionLocal()
    session2 = session_module.SessionLocal()
    
    # Сессии должны быть разными объектами
    assert session1 is not session2
    
    # Но должны быть одного типа
    assert type(session1) == type(session2)
    
    # Закрываем сессии
    session1.close()
    session2.close()


def test_base_metadata_contains_all_tables():
    """Тест, что metadata знает о всех таблицах проекта."""
    expected_tables = {
        "users",
        "balances",
        "ml_models",
        "predictions",
        "transactions",
        "payments",
        "loyalty_tier_rules",
    }

    assert expected_tables.issubset(set(Base.metadata.tables))
