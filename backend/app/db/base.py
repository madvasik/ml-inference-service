from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Импортируем модели после объявления Base, чтобы metadata знала обо всех таблицах.
from backend.app.domain import models  # noqa: F401,E402
