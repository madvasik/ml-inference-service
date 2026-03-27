FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
COPY streamlit_dashboard/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения
COPY streamlit_dashboard/ /app/

# Переменные окружения
ENV PYTHONUNBUFFERED=1

# Команда запуска
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
