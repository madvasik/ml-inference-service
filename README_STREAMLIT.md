# Streamlit Admin Panel

Административная панель для ML Inference Service на базе Streamlit.

## Доступ

Панель доступна по адресу: **http://localhost:8501**

## Возможности

### 👥 Пользователи
- Список всех пользователей
- Статистика по ролям (admin/user)
- График регистраций по датам
- Детальная информация о каждом пользователе

### 🔮 Предсказания
- Список всех предсказаний
- Фильтрация по user_id и model_id
- Статистика по статусам (completed/failed/pending)
- Графики распределения предсказаний
- Детальный просмотр результатов предсказаний

### 💰 Транзакции
- История всех транзакций
- Статистика пополнений и списаний
- Графики транзакций по датам

### 📈 Статистика
- Общие метрики сервиса
- Топ пользователей по активности
- Распределение активности по часам

## Вход

Для входа используйте учетные данные администратора:
- Email: `demo@example.com`
- Password: `demo123`

**Важно:** Пользователь должен иметь роль `admin` в базе данных.

## Назначение администратора

Чтобы сделать пользователя администратором:

```bash
docker-compose exec postgres psql -U user -d ml_service -c \
  "UPDATE users SET role = 'ADMIN' WHERE email = 'ваш_email@example.com';"
```

## Запуск

Панель автоматически запускается вместе с остальными сервисами:

```bash
docker-compose up -d
```

Или отдельно:

```bash
docker-compose up -d streamlit
```

## Локальный запуск (без Docker)

Если хотите запустить панель локально:

1. Установите зависимости:
```bash
pip install -r streamlit_dashboard/requirements.txt
```

2. Измените BASE_URL в `streamlit_dashboard/main.py`:
```python
BASE_URL = "http://localhost:8000"
```

3. Запустите:
```bash
streamlit run streamlit_dashboard/main.py
```
