from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from backend.app.config import settings

# Connection pooling для production
engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=10,  # Количество соединений в пуле
    max_overflow=20,  # Максимальное количество дополнительных соединений
    pool_pre_ping=True,  # Проверка соединений перед использованием
    pool_recycle=3600,  # Переиспользование соединений каждый час
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """Dependency для получения DB сессии"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
