# Структура тестов

Все файлы, относящиеся к тестированию, находятся в этой директории.

## Структура директорий

```
tests/
├── README.md              # Документация
├── conftest.py            # Общие фикстуры pytest
├── test_results.log       # Результаты последнего прогона тестов (полный лог)
├── test_results.json      # JSON сводка результатов
├── test_results.xml       # XML отчет для CI/CD
│
├── unit/                  # Этап 1: Юнит тесты
│   └── test_*.py
│
├── integration/           # Интеграционные тесты
│   └── test_integration.py
│
├── e2e/                   # Этап 2: E2E тесты
│   ├── test_real_world_scenarios.py
│   ├── test_no_crashes.py
│   ├── test_user_flows.py
│   └── utils/
│       └── common_logging.py
│
└── utils/                 # Утилиты тестирования
    ├── run_staged.py      # Скрипт поэтапного запуска
    └── common_logging.py
```

## Этапы тестирования

### Этап 1: Юнит тесты
**Маркер**: `stage1_unit`  
**Директория**: `tests/unit/`  
**Запуск**: `pytest -m stage1_unit`

Быстрые изолированные тесты отдельных компонентов системы.

### Этап 2: E2E сценарии
**Маркер**: `stage2_e2e`  
**Файл**: `tests/e2e/test_real_world_scenarios.py`  
**Запуск**: `python tests/e2e/test_real_world_scenarios.py`

Комплексные тесты реальных пользовательских сценариев.

## Поэтапный запуск всех тестов

```bash
# Из корня проекта
python tests/utils/run_staged.py

# Или как модуль
python -m tests.utils.run_staged
```

## Запуск отдельных этапов

```bash
# Этап 1
pytest -m stage1_unit

# Этап 2
python tests/e2e/test_real_world_scenarios.py
```

## Утилиты

### run_staged.py
Скрипт для поэтапного запуска всех тестов с цветным выводом и сводкой результатов.

### common_logging.py
Общие утилиты для логирования в тестах (находится в `tests/utils/` и `tests/e2e/utils/`).

## Требования

### Для этапа 1
- Python 3.8+
- Установленные зависимости
- Никаких внешних сервисов не требуется

### Для этапа 2
Требуются запущенные сервисы:
- Backend API (localhost:8000)
- Prometheus (localhost:9090)
- Celery Worker
- PostgreSQL

## Результаты тестирования

Результаты последнего прогона тестов сохраняются в файлах:
- `test_results.log` - полный лог выполнения тестов (дублирует консольный вывод)
- `test_results.json` - JSON файл со структурированными данными
- `test_results.xml` - XML отчет для CI/CD систем

**Важно:** Файлы перезаписываются при каждом запуске тестов.

Файл `test_results.log` содержит весь вывод тестов в реальном времени, полностью дублируя то, что выводится в консоль.

## Переменные окружения

```bash
export BASE_URL=http://localhost:8000
export PROMETHEUS_URL=http://localhost:9090
export GRAFANA_URL=http://localhost:3000
```
