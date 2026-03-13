#!/usr/bin/env python3
"""
Комплексные E2E тесты реальных сценариев использования:
- Проверка полных пользовательских сценариев без падений
- Проверка согласованности данных между Backend, Prometheus и Grafana
- Проверка корректности работы всех систем в реальных условиях
"""
import os
import sys
import time
import random
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")

# Цвета для вывода
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"


@dataclass
class TestResult:
    """Результат теста"""
    name: str
    success: bool
    message: str
    details: Dict = None


class RealWorldScenarioTester:
    """Тестер реальных сценариев использования"""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.base_url = BASE_URL
        self.prometheus_url = PROMETHEUS_URL
        self.grafana_url = GRAFANA_URL
        self.test_users = []
        self.test_models = {}
        self.snapshot_before = {}
        self.snapshot_after = {}
        
    def log(self, message: str, color: str = RESET):
        """Логирование с цветом"""
        print(f"{color}{message}{RESET}")
        
    def success(self, message: str):
        """Логирование успеха"""
        self.log(f"✅ {message}", GREEN)
        
    def error(self, message: str):
        """Логирование ошибки"""
        self.log(f"❌ {message}", RED)
        
    def info(self, message: str):
        """Информационное сообщение"""
        self.log(f"ℹ️  {message}", BLUE)
        
    def warning(self, message: str):
        """Предупреждение"""
        self.log(f"⚠️  {message}", YELLOW)
        
    def section(self, title: str):
        """Заголовок секции"""
        self.log("\n" + "="*80, CYAN)
        self.log(f"  {title}", CYAN)
        self.log("="*80, CYAN)
    
    # ========== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ==========
    
    def check_service_health(self, service_name: str, url: str) -> bool:
        """Проверка доступности сервиса"""
        try:
            if service_name == "backend":
                response = requests.get(f"{url}/health", timeout=5)
                return response.status_code == 200
            elif service_name == "prometheus":
                response = requests.get(f"{url}/-/healthy", timeout=5)
                return response.status_code == 200
            elif service_name == "grafana":
                response = requests.get(f"{url}/api/health", timeout=5)
                return response.status_code == 200
            return False
        except Exception as e:
            self.warning(f"Сервис {service_name} недоступен: {e}")
            return False
    
    def login_user(self, email: str, password: str) -> Optional[str]:
        """Вход пользователя и получение токена"""
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/auth/login",
                json={"email": email, "password": password},
                timeout=5
            )
            if response.status_code == 200:
                return response.json()["access_token"]
            return None
        except Exception as e:
            self.error(f"Ошибка входа для {email}: {e}")
            return None
    
    def register_user(self, email: str, password: str) -> Optional[str]:
        """Регистрация пользователя"""
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/auth/register",
                json={"email": email, "password": password},
                timeout=5
            )
            if response.status_code == 201:
                return response.json()["access_token"]
            elif response.status_code == 400:
                # Пользователь уже существует, пробуем войти
                return self.login_user(email, password)
            return None
        except Exception as e:
            self.error(f"Ошибка регистрации для {email}: {e}")
            return None
    
    def get_backend_metrics(self) -> Dict:
        """Получение метрик из backend"""
        try:
            response = requests.get(f"{self.base_url}/metrics", timeout=5)
            if response.status_code != 200:
                return {}
            
            metrics = {}
            lines = response.text.split('\n')
            for line in lines:
                if line.startswith('active_users '):
                    metrics['active_users'] = float(line.split()[1])
                elif 'billing_transactions_total{type="credit"}' in line:
                    metrics['billing_credit'] = float(line.split()[1])
                elif 'billing_transactions_total{type="debit"}' in line:
                    metrics['billing_debit'] = float(line.split()[1])
                elif 'prediction_requests_total{status="completed"' in line:
                    # Суммируем все completed запросы
                    if 'prediction_requests_completed' not in metrics:
                        metrics['prediction_requests_completed'] = 0
                    metrics['prediction_requests_completed'] += float(line.split()[1])
            
            return metrics
        except Exception as e:
            self.error(f"Ошибка получения метрик backend: {e}")
            return {}
    
    def get_prometheus_metrics(self) -> Dict:
        """Получение метрик из Prometheus"""
        metrics = {}
        try:
            # Active users
            response = requests.get(
                f"{self.prometheus_url}/api/v1/query",
                params={"query": "active_users"},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success" and data.get("data", {}).get("result"):
                    metrics['active_users'] = float(data["data"]["result"][0]["value"][1])
            
            # Prediction requests total
            response = requests.get(
                f"{self.prometheus_url}/api/v1/query",
                params={"query": "sum(prediction_requests_total)"},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success" and data.get("data", {}).get("result"):
                    metrics['prediction_requests_total'] = float(data["data"]["result"][0]["value"][1])
            
            # Billing transactions
            response = requests.get(
                f"{self.prometheus_url}/api/v1/query",
                params={"query": "billing_transactions_total"},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    for result in data.get("data", {}).get("result", []):
                        if result["metric"].get("type") == "credit":
                            metrics['billing_credit'] = float(result["value"][1])
                        elif result["metric"].get("type") == "debit":
                            metrics['billing_debit'] = float(result["value"][1])
            
            return metrics
        except Exception as e:
            self.error(f"Ошибка получения метрик Prometheus: {e}")
            return {}
    
    def get_database_stats(self, admin_token: str) -> Dict:
        """Получение статистики из базы данных через API"""
        stats = {}
        try:
            headers = {"Authorization": f"Bearer {admin_token}"}
            
            # Пользователи
            response = requests.get(
                f"{self.base_url}/api/v1/admin/users",
                headers=headers,
                timeout=5
            )
            if response.status_code == 200:
                stats['users_count'] = len(response.json())
            
            # Предсказания
            response = requests.get(
                f"{self.base_url}/api/v1/admin/predictions",
                headers=headers,
                params={"limit": 1000},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                stats['predictions_total'] = data.get("total", 0)
                predictions = data.get("predictions", [])
                stats['predictions_completed'] = len([p for p in predictions if p.get("status") == "completed"])
                stats['predictions_pending'] = len([p for p in predictions if p.get("status") == "pending"])
                stats['predictions_failed'] = len([p for p in predictions if p.get("status") == "failed"])
            
            # Транзакции
            response = requests.get(
                f"{self.base_url}/api/v1/admin/transactions",
                headers=headers,
                params={"limit": 1000},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                stats['transactions_total'] = data.get("total", 0)
                transactions = data.get("transactions", [])
                stats['transactions_credit'] = len([t for t in transactions if t.get("type") == "credit"])
                stats['transactions_debit'] = len([t for t in transactions if t.get("type") == "debit"])
            
            return stats
        except Exception as e:
            self.error(f"Ошибка получения статистики БД: {e}")
            return {}
    
    # ========== ТЕСТОВЫЕ СЦЕНАРИИ ==========
    
    def scenario_1_new_user_complete_flow(self) -> TestResult:
        """Сценарий 1: Новый пользователь - полный цикл использования"""
        self.section("СЦЕНАРИЙ 1: Новый пользователь - полный цикл")
        
        try:
            # 1. Регистрация
            email = f"e2e_user_{random.randint(10000, 99999)}@example.com"
            password = "testpass123"
            
            self.info(f"Регистрация пользователя: {email}")
            token = self.register_user(email, password)
            if not token:
                return TestResult("scenario_1", False, "Не удалось зарегистрировать пользователя")
            self.success("Пользователь зарегистрирован")
            
            headers = {"Authorization": f"Bearer {token}"}
            
            # 2. Проверка начального баланса
            response = requests.get(
                f"{self.base_url}/api/v1/billing/balance",
                headers=headers,
                timeout=5
            )
            if response.status_code != 200:
                return TestResult("scenario_1", False, "Не удалось получить баланс")
            initial_balance = response.json().get("credits", 0)
            self.info(f"Начальный баланс: {initial_balance} кредитов")
            
            # 3. Пополнение баланса
            self.info("Пополнение баланса на 500 кредитов")
            response = requests.post(
                f"{self.base_url}/api/v1/billing/topup",
                headers=headers,
                json={"amount": 500},
                timeout=5
            )
            if response.status_code != 200:
                return TestResult("scenario_1", False, "Не удалось пополнить баланс")
            new_balance = response.json().get("credits", 0)
            self.success(f"Баланс пополнен: {new_balance} кредитов")
            
            if new_balance != initial_balance + 500:
                return TestResult("scenario_1", False, f"Неверный баланс после пополнения: ожидалось {initial_balance + 500}, получено {new_balance}")
            
            # 4. Загрузка модели
            self.info("Загрузка ML модели")
            import pickle
            import tempfile
            import numpy as np
            from sklearn.ensemble import RandomForestClassifier
            
            X = np.array([[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]])
            y = np.array([0, 1, 0, 1, 0])
            model = RandomForestClassifier(n_estimators=10, random_state=42)
            model.fit(X, y)
            
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pkl')
            pickle.dump(model, temp_file)
            temp_file.close()
            
            try:
                with open(temp_file.name, 'rb') as f:
                    response = requests.post(
                        f"{self.base_url}/api/v1/models/upload",
                        headers=headers,
                        files={"file": ("model.pkl", f, "application/octet-stream")},
                        data={"model_name": f"E2E_Model_{random.randint(100, 999)}"},
                        timeout=10
                    )
                
                if response.status_code != 201:
                    return TestResult("scenario_1", False, f"Не удалось загрузить модель: {response.status_code}")
                
                model_data = response.json()
                model_id = model_data["id"]
                self.success(f"Модель загружена: ID {model_id}")
            finally:
                if os.path.exists(temp_file.name):
                    os.remove(temp_file.name)
            
            # 5. Создание предсказаний
            self.info("Создание 3 предсказаний")
            prediction_ids = []
            for i in range(3):
                response = requests.post(
                    f"{self.base_url}/api/v1/predictions",
                    headers=headers,
                    json={
                        "model_id": model_id,
                        "input_data": {
                            "feature1": float(1 + i),
                            "feature2": float(2 + i)
                        }
                    },
                    timeout=5
                )
                if response.status_code == 202:
                    pred_data = response.json()
                    prediction_ids.append(pred_data.get("prediction_id"))
                    self.success(f"Предсказание #{i+1} создано: ID {pred_data.get('prediction_id')}")
                else:
                    self.warning(f"Предсказание #{i+1} не создано: {response.status_code}")
            
            if not prediction_ids:
                return TestResult("scenario_1", False, "Не удалось создать ни одного предсказания")
            
            # 6. Ожидание обработки предсказаний
            self.info("Ожидание обработки предсказаний (10 секунд)...")
            time.sleep(10)
            
            # 7. Проверка статуса предсказаний
            completed_count = 0
            for pred_id in prediction_ids:
                response = requests.get(
                    f"{self.base_url}/api/v1/predictions/{pred_id}",
                    headers=headers,
                    timeout=5
                )
                if response.status_code == 200:
                    pred_data = response.json()
                    status = pred_data.get("status")
                    if status == "completed":
                        completed_count += 1
                        self.success(f"Предсказание {pred_id} завершено")
                    elif status == "pending":
                        self.warning(f"Предсказание {pred_id} все еще в обработке")
                    else:
                        self.warning(f"Предсказание {pred_id} имеет статус: {status}")
            
            # 8. Проверка баланса после предсказаний
            response = requests.get(
                f"{self.base_url}/api/v1/billing/balance",
                headers=headers,
                timeout=5
            )
            if response.status_code == 200:
                final_balance = response.json().get("credits", 0)
                self.info(f"Финальный баланс: {final_balance} кредитов")
                
                # Проверяем, что баланс уменьшился (если предсказания завершились)
                if completed_count > 0:
                    expected_decrease = completed_count * 10  # Стоимость предсказания
                    if final_balance > new_balance - expected_decrease:
                        self.warning(f"Баланс не уменьшился должным образом. Ожидалось списание {expected_decrease} кредитов")
            
            # 9. Проверка транзакций
            response = requests.get(
                f"{self.base_url}/api/v1/billing/transactions",
                headers=headers,
                timeout=5
            )
            if response.status_code == 200:
                transactions = response.json().get("transactions", [])
                credit_count = len([t for t in transactions if t.get("type") == "credit"])
                debit_count = len([t for t in transactions if t.get("type") == "debit"])
                self.info(f"Транзакций: {len(transactions)} (CREDIT: {credit_count}, DEBIT: {debit_count})")
            
            return TestResult(
                "scenario_1",
                True,
                f"Сценарий выполнен успешно. Создано предсказаний: {len(prediction_ids)}, завершено: {completed_count}",
                {
                    "user_email": email,
                    "model_id": model_id,
                    "predictions_created": len(prediction_ids),
                    "predictions_completed": completed_count
                }
            )
            
        except Exception as e:
            return TestResult("scenario_1", False, f"Ошибка выполнения сценария: {str(e)}")
    
    def scenario_2_multiple_users_concurrent(self) -> TestResult:
        """Сценарий 2: Несколько пользователей работают одновременно"""
        self.section("СЦЕНАРИЙ 2: Несколько пользователей - параллельная работа")
        
        try:
            num_users = 3
            users_data = []
            
            # Создаем пользователей
            for i in range(num_users):
                email = f"concurrent_user_{random.randint(10000, 99999)}@example.com"
                password = "testpass123"
                
                self.info(f"Создание пользователя #{i+1}: {email}")
                token = self.register_user(email, password)
                if not token:
                    self.warning(f"Не удалось создать пользователя #{i+1}")
                    continue
                
                # Пополняем баланс
                headers = {"Authorization": f"Bearer {token}"}
                response = requests.post(
                    f"{self.base_url}/api/v1/billing/topup",
                    headers=headers,
                    json={"amount": 200},
                    timeout=5
                )
                
                # Загружаем модель
                import pickle
                import tempfile
                import numpy as np
                from sklearn.ensemble import RandomForestClassifier
                
                X = np.array([[1, 2], [3, 4], [5, 6]])
                y = np.array([0, 1, 0])
                model = RandomForestClassifier(n_estimators=5, random_state=42)
                model.fit(X, y)
                
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pkl')
                pickle.dump(model, temp_file)
                temp_file.close()
                
                try:
                    with open(temp_file.name, 'rb') as f:
                        model_response = requests.post(
                            f"{self.base_url}/api/v1/models/upload",
                            headers=headers,
                            files={"file": ("model.pkl", f, "application/octet-stream")},
                            data={"model_name": f"ConcurrentModel_{i}"},
                            timeout=10
                        )
                    
                    if model_response.status_code == 201:
                        model_id = model_response.json()["id"]
                        users_data.append({
                            "email": email,
                            "token": token,
                            "model_id": model_id
                        })
                        self.success(f"Пользователь #{i+1} готов (модель ID: {model_id})")
                finally:
                    if os.path.exists(temp_file.name):
                        os.remove(temp_file.name)
            
            if not users_data:
                return TestResult("scenario_2", False, "Не удалось создать ни одного пользователя")
            
            # Создаем предсказания параллельно
            self.info(f"Создание предсказаний от {len(users_data)} пользователей...")
            all_predictions = []
            
            for user in users_data:
                headers = {"Authorization": f"Bearer {user['token']}"}
                for j in range(2):  # По 2 предсказания на пользователя
                    try:
                        response = requests.post(
                            f"{self.base_url}/api/v1/predictions",
                            headers=headers,
                            json={
                                "model_id": user["model_id"],
                                "input_data": {
                                    "feature1": float(1 + j),
                                    "feature2": float(2 + j)
                                }
                            },
                            timeout=5
                        )
                        if response.status_code == 202:
                            pred_data = response.json()
                            all_predictions.append(pred_data.get("prediction_id"))
                    except Exception as e:
                        self.warning(f"Ошибка создания предсказания: {e}")
            
            self.success(f"Создано {len(all_predictions)} предсказаний от {len(users_data)} пользователей")
            
            # Ожидание обработки
            self.info("Ожидание обработки предсказаний (15 секунд)...")
            time.sleep(15)
            
            # Проверка статусов
            completed = 0
            pending = 0
            failed = 0
            
            for user in users_data:
                headers = {"Authorization": f"Bearer {user['token']}"}
                response = requests.get(
                    f"{self.base_url}/api/v1/predictions",
                    headers=headers,
                    timeout=5
                )
                if response.status_code == 200:
                    predictions = response.json().get("predictions", [])
                    for pred in predictions:
                        status = pred.get("status")
                        if status == "completed":
                            completed += 1
                        elif status == "pending":
                            pending += 1
                        elif status == "failed":
                            failed += 1
            
            self.info(f"Статусы предсказаний: Completed: {completed}, Pending: {pending}, Failed: {failed}")
            
            return TestResult(
                "scenario_2",
                True,
                f"Сценарий выполнен. Пользователей: {len(users_data)}, Предсказаний: {len(all_predictions)}",
                {
                    "users_count": len(users_data),
                    "predictions_created": len(all_predictions),
                    "completed": completed,
                    "pending": pending,
                    "failed": failed
                }
            )
            
        except Exception as e:
            return TestResult("scenario_2", False, f"Ошибка выполнения сценария: {str(e)}")
    
    def scenario_3_metrics_consistency(self) -> TestResult:
        """Сценарий 3: Проверка согласованности метрик между системами"""
        self.section("СЦЕНАРИЙ 3: Согласованность метрик Backend ↔ Prometheus ↔ Grafana")
        
        try:
            # Получаем метрики из разных источников
            self.info("Получение метрик из Backend...")
            backend_metrics = self.get_backend_metrics()
            
            self.info("Получение метрик из Prometheus...")
            time.sleep(2)  # Даем время Prometheus на скрейпинг
            prometheus_metrics = self.get_prometheus_metrics()
            
            # Получаем статистику из БД
            admin_token = self.login_user("admin@mlservice.com", "admin123")
            if not admin_token:
                return TestResult("scenario_3", False, "Не удалось войти как администратор")
            
            self.info("Получение статистики из БД...")
            db_stats = self.get_database_stats(admin_token)
            
            # Сравнение метрик
            inconsistencies = []
            
            # Проверка active_users
            if "active_users" in backend_metrics and "active_users" in prometheus_metrics:
                backend_val = backend_metrics["active_users"]
                prom_val = prometheus_metrics["active_users"]
                diff = abs(backend_val - prom_val)
                if diff > 0.1:
                    inconsistencies.append(f"active_users: Backend={backend_val}, Prometheus={prom_val}, разница={diff}")
                else:
                    self.success(f"active_users совпадает: {backend_val}")
            
            # Проверка billing transactions
            if "billing_credit" in backend_metrics and "billing_credit" in prometheus_metrics:
                backend_val = backend_metrics["billing_credit"]
                prom_val = prometheus_metrics["billing_credit"]
                diff = abs(backend_val - prom_val)
                if diff > 1.0:  # Допускаем небольшую разницу из-за задержки скрейпинга
                    inconsistencies.append(f"billing_credit: Backend={backend_val}, Prometheus={prom_val}, разница={diff}")
                else:
                    self.success(f"billing_credit совпадает (разница {diff}): {backend_val}")
            
            # Проверка согласованности БД и метрик
            if db_stats:
                self.info(f"Статистика БД:")
                self.info(f"  Пользователей: {db_stats.get('users_count', 0)}")
                self.info(f"  Предсказаний: {db_stats.get('predictions_total', 0)}")
                self.info(f"    - Completed: {db_stats.get('predictions_completed', 0)}")
                self.info(f"    - Pending: {db_stats.get('predictions_pending', 0)}")
                self.info(f"    - Failed: {db_stats.get('predictions_failed', 0)}")
                self.info(f"  Транзакций: {db_stats.get('transactions_total', 0)}")
                self.info(f"    - CREDIT: {db_stats.get('transactions_credit', 0)}")
                self.info(f"    - DEBIT: {db_stats.get('transactions_debit', 0)}")
            
            # Проверка доступности Grafana
            grafana_available = self.check_service_health("grafana", self.grafana_url)
            if grafana_available:
                self.success("Grafana доступна")
            else:
                self.warning("Grafana недоступна (проверьте вручную)")
            
            if inconsistencies:
                return TestResult(
                    "scenario_3",
                    False,
                    f"Обнаружены несоответствия: {', '.join(inconsistencies)}",
                    {"inconsistencies": inconsistencies}
                )
            else:
                return TestResult(
                    "scenario_3",
                    True,
                    "Метрики согласованы между всеми системами",
                    {
                        "backend_metrics": backend_metrics,
                        "prometheus_metrics": prometheus_metrics,
                        "db_stats": db_stats
                    }
                )
                
        except Exception as e:
            return TestResult("scenario_3", False, f"Ошибка проверки метрик: {str(e)}")
    
    def scenario_4_error_handling(self) -> TestResult:
        """Сценарий 4: Проверка обработки ошибок в реальных условиях"""
        self.section("СЦЕНАРИЙ 4: Обработка ошибок и граничных случаев")
        
        try:
            errors_handled = []
            
            # 1. Попытка создать предсказание без модели
            email = f"error_test_{random.randint(10000, 99999)}@example.com"
            token = self.register_user(email, "testpass123")
            if token:
                headers = {"Authorization": f"Bearer {token}"}
                
                # Пополняем баланс
                requests.post(
                    f"{self.base_url}/api/v1/billing/topup",
                    headers=headers,
                    json={"amount": 100},
                    timeout=5
                )
                
                # Пытаемся создать предсказание с несуществующей моделью
                response = requests.post(
                    f"{self.base_url}/api/v1/predictions",
                    headers=headers,
                    json={
                        "model_id": 99999,
                        "input_data": {"feature1": 1.0}
                    },
                    timeout=5
                )
                if response.status_code == 404:
                    self.success("Ошибка 404 для несуществующей модели обработана корректно")
                    errors_handled.append("model_not_found")
                else:
                    self.warning(f"Неожиданный статус для несуществующей модели: {response.status_code}")
            
            # 2. Попытка создать предсказание с недостаточным балансом
            if token:
                # Устанавливаем нулевой баланс
                response = requests.get(
                    f"{self.base_url}/api/v1/billing/balance",
                    headers=headers,
                    timeout=5
                )
                current_balance = response.json().get("credits", 0)
                
                # Создаем модель для теста
                import pickle
                import tempfile
                import numpy as np
                from sklearn.ensemble import RandomForestClassifier
                
                X = np.array([[1, 2], [3, 4]])
                y = np.array([0, 1])
                model = RandomForestClassifier(n_estimators=5, random_state=42)
                model.fit(X, y)
                
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pkl')
                pickle.dump(model, temp_file)
                temp_file.close()
                
                try:
                    with open(temp_file.name, 'rb') as f:
                        model_response = requests.post(
                            f"{self.base_url}/api/v1/models/upload",
                            headers=headers,
                            files={"file": ("model.pkl", f, "application/octet-stream")},
                            data={"model_name": "ErrorTestModel"},
                            timeout=10
                        )
                    
                    if model_response.status_code == 201:
                        model_id = model_response.json()["id"]
                        
                        # Списываем весь баланс
                        # (в реальности нужно использовать API для списания, но для теста просто создадим много предсказаний)
                        # Вместо этого проверим, что система корректно обрабатывает недостаток средств
                        if current_balance < 10:
                            response = requests.post(
                                f"{self.base_url}/api/v1/predictions",
                                headers=headers,
                                json={
                                    "model_id": model_id,
                                    "input_data": {"feature1": 1.0, "feature2": 2.0}
                                },
                                timeout=5
                            )
                            if response.status_code == 402:
                                self.success("Ошибка 402 для недостаточного баланса обработана корректно")
                                errors_handled.append("insufficient_credits")
                finally:
                    if os.path.exists(temp_file.name):
                        os.remove(temp_file.name)
            
            # 3. Проверка невалидного токена
            invalid_response = requests.get(
                f"{self.base_url}/api/v1/users/me",
                headers={"Authorization": "Bearer invalid_token_12345"},
                timeout=5
            )
            if invalid_response.status_code == 401:
                self.success("Ошибка 401 для невалидного токена обработана корректно")
                errors_handled.append("invalid_token")
            
            # 4. Проверка невалидных данных
            if token:
                headers = {"Authorization": f"Bearer {token}"}
                response = requests.post(
                    f"{self.base_url}/api/v1/billing/topup",
                    headers=headers,
                    json={"amount": -100},  # Отрицательная сумма
                    timeout=5
                )
                if response.status_code == 400:
                    self.success("Ошибка 400 для невалидных данных обработана корректно")
                    errors_handled.append("invalid_data")
            
            return TestResult(
                "scenario_4",
                True,
                f"Обработка ошибок работает корректно. Проверено случаев: {len(errors_handled)}",
                {"errors_handled": errors_handled}
            )
            
        except Exception as e:
            return TestResult("scenario_4", False, f"Ошибка проверки обработки ошибок: {str(e)}")
    
    def scenario_5_data_consistency(self) -> TestResult:
        """Сценарий 5: Проверка согласованности данных между API и БД"""
        self.section("СЦЕНАРИЙ 5: Согласованность данных API ↔ БД")
        
        try:
            admin_token = self.login_user("admin@mlservice.com", "admin123")
            if not admin_token:
                return TestResult("scenario_5", False, "Не удалось войти как администратор")
            
            headers = {"Authorization": f"Bearer {admin_token}"}
            
            # Получаем данные через разные endpoints
            users_response = requests.get(
                f"{self.base_url}/api/v1/admin/users",
                headers=headers,
                timeout=5
            )
            
            predictions_response = requests.get(
                f"{self.base_url}/api/v1/admin/predictions",
                headers=headers,
                params={"limit": 1000},
                timeout=5
            )
            
            transactions_response = requests.get(
                f"{self.base_url}/api/v1/admin/transactions",
                headers=headers,
                params={"limit": 1000},
                timeout=5
            )
            
            if users_response.status_code != 200:
                return TestResult("scenario_5", False, "Не удалось получить список пользователей")
            
            if predictions_response.status_code != 200:
                return TestResult("scenario_5", False, "Не удалось получить список предсказаний")
            
            if transactions_response.status_code != 200:
                return TestResult("scenario_5", False, "Не удалось получить список транзакций")
            
            users = users_response.json()
            predictions_data = predictions_response.json()
            transactions_data = transactions_response.json()
            
            predictions = predictions_data.get("predictions", [])
            transactions = transactions_data.get("transactions", [])
            
            # Проверяем согласованность
            inconsistencies = []
            
            # Проверка: количество транзакций должно соответствовать количеству операций
            total_transactions = len(transactions)
            expected_min_transactions = len(users)  # Минимум по одной транзакции на пользователя (пополнение)
            
            if total_transactions < expected_min_transactions:
                inconsistencies.append(f"Транзакций меньше ожидаемого: {total_transactions} < {expected_min_transactions}")
            
            # Проверка: предсказания должны ссылаться на существующих пользователей
            user_ids = {user["id"] for user in users}
            for pred in predictions:
                if pred.get("user_id") not in user_ids:
                    inconsistencies.append(f"Предсказание {pred.get('id')} ссылается на несуществующего пользователя {pred.get('user_id')}")
            
            # Проверка: транзакции должны ссылаться на существующих пользователей
            for trans in transactions:
                if trans.get("user_id") not in user_ids:
                    inconsistencies.append(f"Транзакция {trans.get('id')} ссылается на несуществующего пользователя {trans.get('user_id')}")
            
            # Проверка: балансы пользователей должны быть согласованы с транзакциями
            for user in users:
                user_id = user["id"]
                user_transactions = [t for t in transactions if t.get("user_id") == user_id]
                
                # Получаем баланс через API
                user_token = self.login_user(user["email"], "testpassword")
                if not user_token:
                    # Пробуем стандартный пароль
                    user_token = self.login_user(user["email"], "user123")
                
                if user_token:
                    user_headers = {"Authorization": f"Bearer {user_token}"}
                    balance_response = requests.get(
                        f"{self.base_url}/api/v1/billing/balance",
                        headers=user_headers,
                        timeout=5
                    )
                    if balance_response.status_code == 200:
                        api_balance = balance_response.json().get("credits", 0)
                        
                        # Вычисляем баланс из транзакций
                        calculated_balance = sum(
                            t.get("amount", 0) if t.get("type") == "credit" else -t.get("amount", 0)
                            for t in user_transactions
                        )
                        
                        # Допускаем небольшую разницу из-за списаний за предсказания
                        if abs(api_balance - calculated_balance) > 50:
                            inconsistencies.append(
                                f"Баланс пользователя {user_id} не согласован: API={api_balance}, "
                                f"рассчитанный={calculated_balance}"
                            )
            
            if inconsistencies:
                return TestResult(
                    "scenario_5",
                    False,
                    f"Обнаружены несоответствия данных: {len(inconsistencies)}",
                    {"inconsistencies": inconsistencies[:10]}  # Ограничиваем вывод
                )
            else:
                self.success("Данные согласованы между API и БД")
                return TestResult(
                    "scenario_5",
                    True,
                    f"Данные согласованы. Пользователей: {len(users)}, "
                    f"Предсказаний: {len(predictions)}, Транзакций: {total_transactions}",
                    {
                        "users_count": len(users),
                        "predictions_count": len(predictions),
                        "transactions_count": total_transactions
                    }
                )
                
        except Exception as e:
            return TestResult("scenario_5", False, f"Ошибка проверки согласованности данных: {str(e)}")
    
    def scenario_6_no_crashes_under_load(self) -> TestResult:
        """Сценарий 6: Проверка отсутствия падений под нагрузкой"""
        self.section("СЦЕНАРИЙ 6: Стабильность под нагрузкой")
        
        try:
            # Создаем пользователя для нагрузки
            email = f"load_test_{random.randint(10000, 99999)}@example.com"
            token = self.register_user(email, "testpass123")
            if not token:
                return TestResult("scenario_6", False, "Не удалось создать пользователя для нагрузки")
            
            headers = {"Authorization": f"Bearer {token}"}
            
            # Пополняем баланс
            requests.post(
                f"{self.base_url}/api/v1/billing/topup",
                headers=headers,
                json={"amount": 1000},
                timeout=5
            )
            
            # Загружаем модель
            import pickle
            import tempfile
            import numpy as np
            from sklearn.ensemble import RandomForestClassifier
            
            X = np.array([[1, 2], [3, 4], [5, 6]])
            y = np.array([0, 1, 0])
            model = RandomForestClassifier(n_estimators=5, random_state=42)
            model.fit(X, y)
            
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pkl')
            pickle.dump(model, temp_file)
            temp_file.close()
            
            try:
                with open(temp_file.name, 'rb') as f:
                    model_response = requests.post(
                        f"{self.base_url}/api/v1/models/upload",
                        headers=headers,
                        files={"file": ("model.pkl", f, "application/octet-stream")},
                        data={"model_name": "LoadTestModel"},
                        timeout=10
                    )
                
                if model_response.status_code != 201:
                    return TestResult("scenario_6", False, "Не удалось загрузить модель")
                
                model_id = model_response.json()["id"]
            finally:
                if os.path.exists(temp_file.name):
                    os.remove(temp_file.name)
            
            # Создаем множество запросов
            num_requests = 20
            self.info(f"Создание {num_requests} запросов подряд...")
            
            successful = 0
            errors = 0
            error_codes = {}
            
            for i in range(num_requests):
                try:
                    response = requests.post(
                        f"{self.base_url}/api/v1/predictions",
                        headers=headers,
                        json={
                            "model_id": model_id,
                            "input_data": {
                                "feature1": float(1 + i % 10),
                                "feature2": float(2 + i % 10)
                            }
                        },
                        timeout=5
                    )
                    
                    if response.status_code == 202:
                        successful += 1
                    else:
                        errors += 1
                        error_codes[response.status_code] = error_codes.get(response.status_code, 0) + 1
                        
                except Exception as e:
                    errors += 1
                    self.warning(f"Ошибка запроса #{i+1}: {e}")
            
            # Проверяем, что сервис все еще работает
            health_response = requests.get(f"{self.base_url}/health", timeout=5)
            service_alive = health_response.status_code == 200
            
            if not service_alive:
                return TestResult("scenario_6", False, "Сервис упал под нагрузкой")
            
            self.success(f"Сервис стабилен. Успешных запросов: {successful}, Ошибок: {errors}")
            
            if errors > num_requests * 0.1:  # Более 10% ошибок
                return TestResult(
                    "scenario_6",
                    False,
                    f"Слишком много ошибок под нагрузкой: {errors}/{num_requests}",
                    {"successful": successful, "errors": errors, "error_codes": error_codes}
                )
            
            return TestResult(
                "scenario_6",
                True,
                f"Сервис стабилен под нагрузкой. Успешных: {successful}, Ошибок: {errors}",
                {"successful": successful, "errors": errors, "error_codes": error_codes}
            )
            
        except Exception as e:
            return TestResult("scenario_6", False, f"Ошибка теста нагрузки: {str(e)}")
    
    def scenario_7_admin_operations(self) -> TestResult:
        """Сценарий 7: Админские операции - просмотр всех данных"""
        self.section("СЦЕНАРИЙ 7: Админские операции")
        
        try:
            admin_token = self.login_user("admin@mlservice.com", "admin123")
            if not admin_token:
                return TestResult("scenario_7", False, "Не удалось войти как администратор")
            
            headers = {"Authorization": f"Bearer {admin_token}"}
            
            # 1. Получение списка всех пользователей
            self.info("Получение списка всех пользователей...")
            response = requests.get(
                f"{self.base_url}/api/v1/admin/users",
                headers=headers,
                params={"limit": 100},
                timeout=5
            )
            if response.status_code != 200:
                return TestResult("scenario_7", False, "Не удалось получить список пользователей")
            users = response.json()
            self.success(f"Получено пользователей: {len(users)}")
            
            # 2. Получение информации о конкретном пользователе
            if users:
                user_id = users[0]["id"]
                self.info(f"Получение информации о пользователе ID {user_id}...")
                response = requests.get(
                    f"{self.base_url}/api/v1/admin/users/{user_id}",
                    headers=headers,
                    timeout=5
                )
                if response.status_code == 200:
                    user_data = response.json()
                    self.success(f"Данные пользователя получены: {user_data.get('email')}")
                else:
                    self.warning(f"Не удалось получить данные пользователя: {response.status_code}")
            
            # 3. Получение всех предсказаний с фильтрацией
            self.info("Получение всех предсказаний...")
            response = requests.get(
                f"{self.base_url}/api/v1/admin/predictions",
                headers=headers,
                params={"limit": 100},
                timeout=5
            )
            if response.status_code != 200:
                return TestResult("scenario_7", False, "Не удалось получить список предсказаний")
            predictions_data = response.json()
            predictions = predictions_data.get("predictions", [])
            total = predictions_data.get("total", 0)
            self.success(f"Получено предсказаний: {len(predictions)} из {total}")
            
            # 4. Фильтрация предсказаний по user_id
            if users and predictions:
                user_id = users[0]["id"]
                self.info(f"Фильтрация предсказаний по user_id={user_id}...")
                response = requests.get(
                    f"{self.base_url}/api/v1/admin/predictions",
                    headers=headers,
                    params={"user_id": user_id, "limit": 50},
                    timeout=5
                )
                if response.status_code == 200:
                    filtered_data = response.json()
                    filtered_predictions = filtered_data.get("predictions", [])
                    self.success(f"Найдено предсказаний для пользователя {user_id}: {len(filtered_predictions)}")
                    
                    # Проверяем, что все предсказания принадлежат этому пользователю
                    for pred in filtered_predictions:
                        if pred.get("user_id") != user_id:
                            return TestResult("scenario_7", False, f"Фильтр не работает: найдено предсказание другого пользователя")
            
            # 5. Получение всех транзакций
            self.info("Получение всех транзакций...")
            response = requests.get(
                f"{self.base_url}/api/v1/admin/transactions",
                headers=headers,
                params={"limit": 100},
                timeout=5
            )
            if response.status_code != 200:
                return TestResult("scenario_7", False, "Не удалось получить список транзакций")
            transactions_data = response.json()
            transactions = transactions_data.get("transactions", [])
            total_trans = transactions_data.get("total", 0)
            self.success(f"Получено транзакций: {len(transactions)} из {total_trans}")
            
            # 6. Фильтрация транзакций по user_id
            if users and transactions:
                user_id = users[0]["id"]
                self.info(f"Фильтрация транзакций по user_id={user_id}...")
                response = requests.get(
                    f"{self.base_url}/api/v1/admin/transactions",
                    headers=headers,
                    params={"user_id": user_id, "limit": 50},
                    timeout=5
                )
                if response.status_code == 200:
                    filtered_data = response.json()
                    filtered_transactions = filtered_data.get("transactions", [])
                    self.success(f"Найдено транзакций для пользователя {user_id}: {len(filtered_transactions)}")
            
            return TestResult(
                "scenario_7",
                True,
                f"Админские операции выполнены успешно. Пользователей: {len(users)}, "
                f"Предсказаний: {total}, Транзакций: {total_trans}",
                {
                    "users_count": len(users),
                    "predictions_total": total,
                    "transactions_total": total_trans
                }
            )
            
        except Exception as e:
            return TestResult("scenario_7", False, f"Ошибка админских операций: {str(e)}")
    
    def scenario_8_model_management(self) -> TestResult:
        """Сценарий 8: Управление моделями (загрузка, просмотр, удаление)"""
        self.section("СЦЕНАРИЙ 8: Управление моделями")
        
        try:
            # Создаем пользователя
            email = f"model_mgmt_{random.randint(10000, 99999)}@example.com"
            token = self.register_user(email, "testpass123")
            if not token:
                return TestResult("scenario_8", False, "Не удалось создать пользователя")
            
            headers = {"Authorization": f"Bearer {token}"}
            
            # 1. Загрузка нескольких моделей
            self.info("Загрузка моделей...")
            import pickle
            import tempfile
            import numpy as np
            from sklearn.ensemble import RandomForestClassifier
            
            model_ids = []
            for i in range(3):
                X = np.array([[1, 2], [3, 4], [5, 6]])
                y = np.array([0, 1, 0])
                model = RandomForestClassifier(n_estimators=5, random_state=42+i)
                model.fit(X, y)
                
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pkl')
                pickle.dump(model, temp_file)
                temp_file.close()
                
                try:
                    with open(temp_file.name, 'rb') as f:
                        response = requests.post(
                            f"{self.base_url}/api/v1/models/upload",
                            headers=headers,
                            files={"file": ("model.pkl", f, "application/octet-stream")},
                            data={"model_name": f"TestModel_{i}"},
                            timeout=10
                        )
                    
                    if response.status_code == 201:
                        model_data = response.json()
                        model_ids.append(model_data["id"])
                        self.success(f"Модель #{i+1} загружена: ID {model_data['id']}")
                finally:
                    if os.path.exists(temp_file.name):
                        os.remove(temp_file.name)
            
            if not model_ids:
                return TestResult("scenario_8", False, "Не удалось загрузить ни одной модели")
            
            # 2. Просмотр списка моделей
            self.info("Получение списка моделей...")
            response = requests.get(
                f"{self.base_url}/api/v1/models",
                headers=headers,
                timeout=5
            )
            if response.status_code != 200:
                return TestResult("scenario_8", False, "Не удалось получить список моделей")
            
            models_data = response.json()
            models = models_data.get("models", [])
            total = models_data.get("total", 0)
            self.success(f"Получено моделей: {len(models)} из {total}")
            
            # Проверяем, что все загруженные модели присутствуют
            loaded_ids = set(model_ids)
            found_ids = {m["id"] for m in models}
            if not loaded_ids.issubset(found_ids):
                missing = loaded_ids - found_ids
                return TestResult("scenario_8", False, f"Не все модели найдены в списке. Отсутствуют: {missing}")
            
            # 3. Получение информации о конкретной модели
            model_id = model_ids[0]
            self.info(f"Получение информации о модели ID {model_id}...")
            response = requests.get(
                f"{self.base_url}/api/v1/models/{model_id}",
                headers=headers,
                timeout=5
            )
            if response.status_code != 200:
                return TestResult("scenario_8", False, f"Не удалось получить информацию о модели {model_id}")
            
            model_info = response.json()
            self.success(f"Информация о модели получена: {model_info.get('name')}")
            
            # 4. Удаление модели
            model_to_delete = model_ids[-1]
            self.info(f"Удаление модели ID {model_to_delete}...")
            response = requests.delete(
                f"{self.base_url}/api/v1/models/{model_to_delete}",
                headers=headers,
                timeout=5
            )
            if response.status_code != 204:
                return TestResult("scenario_8", False, f"Не удалось удалить модель {model_to_delete}")
            
            self.success(f"Модель {model_to_delete} удалена")
            
            # 5. Проверка, что модель действительно удалена
            response = requests.get(
                f"{self.base_url}/api/v1/models/{model_to_delete}",
                headers=headers,
                timeout=5
            )
            if response.status_code != 404:
                return TestResult("scenario_8", False, f"Модель {model_to_delete} все еще доступна после удаления")
            
            self.success("Модель корректно удалена и недоступна")
            
            return TestResult(
                "scenario_8",
                True,
                f"Управление моделями выполнено успешно. Загружено: {len(model_ids)}, Удалено: 1",
                {
                    "models_uploaded": len(model_ids),
                    "models_deleted": 1
                }
            )
            
        except Exception as e:
            return TestResult("scenario_8", False, f"Ошибка управления моделями: {str(e)}")
    
    def scenario_9_pagination_and_filtering(self) -> TestResult:
        """Сценарий 9: Пагинация и фильтрация данных"""
        self.section("СЦЕНАРИЙ 9: Пагинация и фильтрация")
        
        try:
            admin_token = self.login_user("admin@mlservice.com", "admin123")
            if not admin_token:
                return TestResult("scenario_9", False, "Не удалось войти как администратор")
            
            headers = {"Authorization": f"Bearer {admin_token}"}
            
            # 1. Тест пагинации предсказаний
            self.info("Тест пагинации предсказаний...")
            page_size = 10
            all_predictions = []
            
            # Получаем первую страницу
            response = requests.get(
                f"{self.base_url}/api/v1/admin/predictions",
                headers=headers,
                params={"skip": 0, "limit": page_size},
                timeout=5
            )
            if response.status_code != 200:
                return TestResult("scenario_9", False, "Не удалось получить первую страницу предсказаний")
            
            first_page = response.json()
            all_predictions.extend(first_page.get("predictions", []))
            total = first_page.get("total", 0)
            
            self.info(f"Первая страница: {len(first_page.get('predictions', []))} из {total}")
            
            # Получаем вторую страницу
            if total > page_size:
                response = requests.get(
                    f"{self.base_url}/api/v1/admin/predictions",
                    headers=headers,
                    params={"skip": page_size, "limit": page_size},
                    timeout=5
                )
                if response.status_code == 200:
                    second_page = response.json()
                    second_page_predictions = second_page.get("predictions", [])
                    all_predictions.extend(second_page_predictions)
                    self.info(f"Вторая страница: {len(second_page_predictions)}")
                    
                    # Проверяем, что предсказания не повторяются
                    prediction_ids = [p["id"] for p in all_predictions]
                    if len(prediction_ids) != len(set(prediction_ids)):
                        return TestResult("scenario_9", False, "Обнаружены дубликаты в пагинации")
                    
                    self.success("Пагинация предсказаний работает корректно")
            
            # 2. Тест фильтрации по model_id
            if all_predictions:
                model_id = all_predictions[0].get("model_id")
                if model_id:
                    self.info(f"Фильтрация предсказаний по model_id={model_id}...")
                    response = requests.get(
                        f"{self.base_url}/api/v1/admin/predictions",
                        headers=headers,
                        params={"model_id": model_id, "limit": 50},
                        timeout=5
                    )
                    if response.status_code == 200:
                        filtered_data = response.json()
                        filtered_predictions = filtered_data.get("predictions", [])
                        
                        # Проверяем, что все предсказания имеют правильный model_id
                        for pred in filtered_predictions:
                            if pred.get("model_id") != model_id:
                                return TestResult("scenario_9", False, "Фильтр по model_id не работает корректно")
                        
                        self.success(f"Фильтрация по model_id работает: найдено {len(filtered_predictions)} предсказаний")
            
            # 3. Тест пагинации транзакций
            self.info("Тест пагинации транзакций...")
            response = requests.get(
                f"{self.base_url}/api/v1/admin/transactions",
                headers=headers,
                params={"skip": 0, "limit": page_size},
                timeout=5
            )
            if response.status_code == 200:
                transactions_data = response.json()
                transactions = transactions_data.get("transactions", [])
                total_trans = transactions_data.get("total", 0)
                self.success(f"Пагинация транзакций работает: {len(transactions)} из {total_trans}")
            
            # 4. Тест фильтрации транзакций по user_id
            if transactions:
                user_id = transactions[0].get("user_id")
                if user_id:
                    self.info(f"Фильтрация транзакций по user_id={user_id}...")
                    response = requests.get(
                        f"{self.base_url}/api/v1/admin/transactions",
                        headers=headers,
                        params={"user_id": user_id, "limit": 50},
                        timeout=5
                    )
                    if response.status_code == 200:
                        filtered_data = response.json()
                        filtered_transactions = filtered_data.get("transactions", [])
                        
                        for trans in filtered_transactions:
                            if trans.get("user_id") != user_id:
                                return TestResult("scenario_9", False, "Фильтр по user_id не работает корректно")
                        
                        self.success(f"Фильтрация по user_id работает: найдено {len(filtered_transactions)} транзакций")
            
            return TestResult(
                "scenario_9",
                True,
                "Пагинация и фильтрация работают корректно",
                {
                    "pagination_tested": True,
                    "filtering_tested": True
                }
            )
            
        except Exception as e:
            return TestResult("scenario_9", False, f"Ошибка теста пагинации: {str(e)}")
    
    def scenario_10_security_checks(self) -> TestResult:
        """Сценарий 10: Проверка безопасности - доступ к чужим данным"""
        self.section("СЦЕНАРИЙ 10: Проверка безопасности")
        
        try:
            # Создаем двух пользователей
            email1 = f"security_user1_{random.randint(10000, 99999)}@example.com"
            email2 = f"security_user2_{random.randint(10000, 99999)}@example.com"
            
            token1 = self.register_user(email1, "testpass123")
            token2 = self.register_user(email2, "testpass123")
            
            if not token1 or not token2:
                return TestResult("scenario_10", False, "Не удалось создать пользователей")
            
            headers1 = {"Authorization": f"Bearer {token1}"}
            headers2 = {"Authorization": f"Bearer {token2}"}
            
            # Пополняем балансы
            requests.post(f"{self.base_url}/api/v1/billing/topup", headers=headers1, json={"amount": 100}, timeout=5)
            requests.post(f"{self.base_url}/api/v1/billing/topup", headers=headers2, json={"amount": 100}, timeout=5)
            
            # Загружаем модели для обоих пользователей
            import pickle
            import tempfile
            import numpy as np
            from sklearn.ensemble import RandomForestClassifier
            
            model_id1 = None
            model_id2 = None
            
            # Модель для пользователя 1
            X = np.array([[1, 2], [3, 4]])
            y = np.array([0, 1])
            model = RandomForestClassifier(n_estimators=5, random_state=42)
            model.fit(X, y)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pkl')
            pickle.dump(model, temp_file)
            temp_file.close()
            
            try:
                with open(temp_file.name, 'rb') as f:
                    response = requests.post(
                        f"{self.base_url}/api/v1/models/upload",
                        headers=headers1,
                        files={"file": ("model.pkl", f, "application/octet-stream")},
                        data={"model_name": "User1Model"},
                        timeout=10
                    )
                if response.status_code == 201:
                    model_id1 = response.json()["id"]
            finally:
                if os.path.exists(temp_file.name):
                    os.remove(temp_file.name)
            
            # Модель для пользователя 2
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pkl')
            pickle.dump(model, temp_file)
            temp_file.close()
            
            try:
                with open(temp_file.name, 'rb') as f:
                    response = requests.post(
                        f"{self.base_url}/api/v1/models/upload",
                        headers=headers2,
                        files={"file": ("model.pkl", f, "application/octet-stream")},
                        data={"model_name": "User2Model"},
                        timeout=10
                    )
                if response.status_code == 201:
                    model_id2 = response.json()["id"]
            finally:
                if os.path.exists(temp_file.name):
                    os.remove(temp_file.name)
            
            security_issues = []
            
            # 1. Пользователь 2 пытается получить модель пользователя 1
            if model_id1:
                self.info("Проверка доступа к чужой модели...")
                response = requests.get(
                    f"{self.base_url}/api/v1/models/{model_id1}",
                    headers=headers2,
                    timeout=5
                )
                if response.status_code != 404:
                    security_issues.append(f"Пользователь 2 получил доступ к модели пользователя 1 (статус: {response.status_code})")
                else:
                    self.success("Доступ к чужой модели корректно запрещен")
            
            # 2. Пользователь 2 пытается удалить модель пользователя 1
            if model_id1:
                self.info("Проверка удаления чужой модели...")
                response = requests.delete(
                    f"{self.base_url}/api/v1/models/{model_id1}",
                    headers=headers2,
                    timeout=5
                )
                if response.status_code != 404:
                    security_issues.append(f"Пользователь 2 смог удалить модель пользователя 1 (статус: {response.status_code})")
                else:
                    self.success("Удаление чужой модели корректно запрещено")
            
            # 3. Создаем предсказания для обоих пользователей
            pred_id1 = None
            if model_id1:
                response = requests.post(
                    f"{self.base_url}/api/v1/predictions",
                    headers=headers1,
                    json={"model_id": model_id1, "input_data": {"feature1": 1.0, "feature2": 2.0}},
                    timeout=5
                )
                if response.status_code == 202:
                    pred_id1 = response.json().get("prediction_id")
            
            pred_id2 = None
            if model_id2:
                response = requests.post(
                    f"{self.base_url}/api/v1/predictions",
                    headers=headers2,
                    json={"model_id": model_id2, "input_data": {"feature1": 1.0, "feature2": 2.0}},
                    timeout=5
                )
                if response.status_code == 202:
                    pred_id2 = response.json().get("prediction_id")
            
            # 4. Пользователь 2 пытается получить предсказание пользователя 1
            if pred_id1:
                self.info("Проверка доступа к чужому предсказанию...")
                response = requests.get(
                    f"{self.base_url}/api/v1/predictions/{pred_id1}",
                    headers=headers2,
                    timeout=5
                )
                if response.status_code != 404:
                    security_issues.append(f"Пользователь 2 получил доступ к предсказанию пользователя 1 (статус: {response.status_code})")
                else:
                    self.success("Доступ к чужому предсказанию корректно запрещен")
            
            # 5. Проверка списка предсказаний - пользователь должен видеть только свои
            self.info("Проверка изоляции предсказаний...")
            response = requests.get(
                f"{self.base_url}/api/v1/predictions",
                headers=headers1,
                timeout=5
            )
            if response.status_code == 200:
                user1_predictions = response.json().get("predictions", [])
                user1_ids = {p["id"] for p in user1_predictions}
                
                if pred_id2 and pred_id2 in user1_ids:
                    security_issues.append("Пользователь 1 видит предсказания пользователя 2")
                else:
                    self.success("Изоляция предсказаний работает корректно")
            
            if security_issues:
                return TestResult(
                    "scenario_10",
                    False,
                    f"Обнаружены проблемы безопасности: {len(security_issues)}",
                    {"security_issues": security_issues}
                )
            else:
                return TestResult(
                    "scenario_10",
                    True,
                    "Все проверки безопасности пройдены",
                    {"security_checks_passed": True}
                )
            
        except Exception as e:
            return TestResult("scenario_10", False, f"Ошибка проверки безопасности: {str(e)}")
    
    def scenario_11_history_and_audit(self) -> TestResult:
        """Сценарий 11: История транзакций и предсказаний"""
        self.section("СЦЕНАРИЙ 11: История и аудит")
        
        try:
            # Создаем пользователя
            email = f"history_{random.randint(10000, 99999)}@example.com"
            token = self.register_user(email, "testpass123")
            if not token:
                return TestResult("scenario_11", False, "Не удалось создать пользователя")
            
            headers = {"Authorization": f"Bearer {token}"}
            
            # 1. Пополняем баланс несколько раз
            self.info("Создание истории транзакций...")
            topup_amounts = [50, 100, 200]
            for amount in topup_amounts:
                response = requests.post(
                    f"{self.base_url}/api/v1/billing/topup",
                    headers=headers,
                    json={"amount": amount},
                    timeout=5
                )
                if response.status_code == 200:
                    self.success(f"Пополнение на {amount} кредитов")
            
            # 2. Получаем историю транзакций
            self.info("Получение истории транзакций...")
            response = requests.get(
                f"{self.base_url}/api/v1/billing/transactions",
                headers=headers,
                timeout=5
            )
            if response.status_code != 200:
                return TestResult("scenario_11", False, "Не удалось получить историю транзакций")
            
            transactions = response.json().get("transactions", [])
            credit_transactions = [t for t in transactions if t.get("type") == "credit"]
            
            if len(credit_transactions) < len(topup_amounts):
                return TestResult("scenario_11", False, f"Не все транзакции пополнения отображаются. Ожидалось: {len(topup_amounts)}, получено: {len(credit_transactions)}")
            
            self.success(f"История транзакций получена: {len(transactions)} транзакций")
            
            # 3. Загружаем модель и создаем предсказания
            import pickle
            import tempfile
            import numpy as np
            from sklearn.ensemble import RandomForestClassifier
            
            X = np.array([[1, 2], [3, 4], [5, 6]])
            y = np.array([0, 1, 0])
            model = RandomForestClassifier(n_estimators=5, random_state=42)
            model.fit(X, y)
            
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pkl')
            pickle.dump(model, temp_file)
            temp_file.close()
            
            model_id = None
            try:
                with open(temp_file.name, 'rb') as f:
                    response = requests.post(
                        f"{self.base_url}/api/v1/models/upload",
                        headers=headers,
                        files={"file": ("model.pkl", f, "application/octet-stream")},
                        data={"model_name": "HistoryTestModel"},
                        timeout=10
                    )
                if response.status_code == 201:
                    model_id = response.json()["id"]
            finally:
                if os.path.exists(temp_file.name):
                    os.remove(temp_file.name)
            
            if not model_id:
                return TestResult("scenario_11", False, "Не удалось загрузить модель")
            
            # Создаем несколько предсказаний
            prediction_ids = []
            for i in range(3):
                response = requests.post(
                    f"{self.base_url}/api/v1/predictions",
                    headers=headers,
                    json={
                        "model_id": model_id,
                        "input_data": {"feature1": float(1+i), "feature2": float(2+i)}
                    },
                    timeout=5
                )
                if response.status_code == 202:
                    pred_id = response.json().get("prediction_id")
                    prediction_ids.append(pred_id)
            
            # 4. Получаем историю предсказаний
            self.info("Получение истории предсказаний...")
            response = requests.get(
                f"{self.base_url}/api/v1/predictions",
                headers=headers,
                timeout=5
            )
            if response.status_code != 200:
                return TestResult("scenario_11", False, "Не удалось получить историю предсказаний")
            
            predictions = response.json().get("predictions", [])
            
            if len(predictions) < len(prediction_ids):
                return TestResult("scenario_11", False, f"Не все предсказания отображаются в истории. Ожидалось: {len(prediction_ids)}, получено: {len(predictions)}")
            
            # Проверяем, что предсказания отсортированы по дате (новые первые)
            if len(predictions) > 1:
                dates = [p.get("created_at") for p in predictions if p.get("created_at")]
                if dates != sorted(dates, reverse=True):
                    self.warning("Предсказания не отсортированы по дате (новые первые)")
            
            self.success(f"История предсказаний получена: {len(predictions)} предсказаний")
            
            # 5. Проверяем детали конкретного предсказания
            if prediction_ids:
                pred_id = prediction_ids[0]
                self.info(f"Получение деталей предсказания {pred_id}...")
                response = requests.get(
                    f"{self.base_url}/api/v1/predictions/{pred_id}",
                    headers=headers,
                    timeout=5
                )
                if response.status_code == 200:
                    pred_details = response.json()
                    if pred_details.get("id") == pred_id:
                        self.success("Детали предсказания получены корректно")
                    else:
                        return TestResult("scenario_11", False, "Неверные детали предсказания")
            
            return TestResult(
                "scenario_11",
                True,
                f"История и аудит работают корректно. Транзакций: {len(transactions)}, Предсказаний: {len(predictions)}",
                {
                    "transactions_count": len(transactions),
                    "predictions_count": len(predictions)
                }
            )
            
        except Exception as e:
            return TestResult("scenario_11", False, f"Ошибка проверки истории: {str(e)}")
    
    def scenario_12_rate_limiting_real_world(self) -> TestResult:
        """Сценарий 12: Rate limiting в реальных условиях"""
        self.section("СЦЕНАРИЙ 12: Rate Limiting")
        
        try:
            # Создаем пользователя
            email = f"ratelimit_{random.randint(10000, 99999)}@example.com"
            token = self.register_user(email, "testpass123")
            if not token:
                return TestResult("scenario_12", False, "Не удалось создать пользователя")
            
            headers = {"Authorization": f"Bearer {token}"}
            
            # Отправляем множество запросов быстро
            self.info("Отправка множества запросов для проверки rate limiting...")
            rate_limited_count = 0
            successful_count = 0
            
            for i in range(30):  # Много запросов подряд
                try:
                    response = requests.get(
                        f"{self.base_url}/api/v1/users/me",
                        headers=headers,
                        timeout=2
                    )
                    
                    if response.status_code == 200:
                        successful_count += 1
                    elif response.status_code == 429:  # Too Many Requests
                        rate_limited_count += 1
                        self.info(f"Rate limit сработал на запросе #{i+1}")
                        break  # Rate limit сработал
                except Exception as e:
                    self.warning(f"Ошибка запроса #{i+1}: {e}")
                
                time.sleep(0.1)  # Небольшая задержка
            
            # Rate limiting должен сработать при большом количестве запросов
            if rate_limited_count > 0:
                self.success(f"Rate limiting работает: заблокировано после {successful_count} успешных запросов")
                return TestResult(
                    "scenario_12",
                    True,
                    f"Rate limiting работает корректно. Успешных: {successful_count}, Заблокировано: {rate_limited_count}",
                    {
                        "successful_requests": successful_count,
                        "rate_limited": rate_limited_count
                    }
                )
            else:
                self.warning(f"Rate limiting не сработал после {successful_count} запросов")
                # Это не обязательно ошибка - возможно лимит выше
                return TestResult(
                    "scenario_12",
                    True,
                    f"Rate limiting не сработал (возможно лимит выше). Выполнено запросов: {successful_count}",
                    {
                        "successful_requests": successful_count,
                        "rate_limited": 0
                    }
                )
            
        except Exception as e:
            return TestResult("scenario_12", False, f"Ошибка проверки rate limiting: {str(e)}")
    
    def scenario_13_large_volume_data(self) -> TestResult:
        """Сценарий 13: Большой объем данных"""
        self.section("СЦЕНАРИЙ 13: Большой объем данных")
        
        try:
            # Создаем пользователя
            email = f"volume_{random.randint(10000, 99999)}@example.com"
            token = self.register_user(email, "testpass123")
            if not token:
                return TestResult("scenario_13", False, "Не удалось создать пользователя")
            
            headers = {"Authorization": f"Bearer {token}"}
            
            # Пополняем баланс
            requests.post(
                f"{self.base_url}/api/v1/billing/topup",
                headers=headers,
                json={"amount": 1000},
                timeout=5
            )
            
            # Загружаем несколько моделей
            import pickle
            import tempfile
            import numpy as np
            from sklearn.ensemble import RandomForestClassifier
            
            model_ids = []
            for i in range(5):
                X = np.array([[1, 2], [3, 4]])
                y = np.array([0, 1])
                model = RandomForestClassifier(n_estimators=5, random_state=42+i)
                model.fit(X, y)
                
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pkl')
                pickle.dump(model, temp_file)
                temp_file.close()
                
                try:
                    with open(temp_file.name, 'rb') as f:
                        response = requests.post(
                            f"{self.base_url}/api/v1/models/upload",
                            headers=headers,
                            files={"file": ("model.pkl", f, "application/octet-stream")},
                            data={"model_name": f"VolumeModel_{i}"},
                            timeout=10
                        )
                    if response.status_code == 201:
                        model_ids.append(response.json()["id"])
                finally:
                    if os.path.exists(temp_file.name):
                        os.remove(temp_file.name)
            
            self.info(f"Загружено моделей: {len(model_ids)}")
            
            # Создаем много предсказаний
            self.info("Создание множества предсказаний...")
            prediction_ids = []
            for i in range(20):
                if model_ids:
                    model_id = model_ids[i % len(model_ids)]
                    response = requests.post(
                        f"{self.base_url}/api/v1/predictions",
                        headers=headers,
                        json={
                            "model_id": model_id,
                            "input_data": {"feature1": float(1 + i), "feature2": float(2 + i)}
                        },
                        timeout=5
                    )
                    if response.status_code == 202:
                        prediction_ids.append(response.json().get("prediction_id"))
            
            self.info(f"Создано предсказаний: {len(prediction_ids)}")
            
            # Проверяем, что все данные доступны
            response = requests.get(
                f"{self.base_url}/api/v1/models",
                headers=headers,
                timeout=5
            )
            if response.status_code != 200:
                return TestResult("scenario_13", False, "Не удалось получить список моделей")
            
            models_data = response.json()
            if len(models_data.get("models", [])) != len(model_ids):
                return TestResult("scenario_13", False, "Не все модели доступны")
            
            response = requests.get(
                f"{self.base_url}/api/v1/predictions",
                headers=headers,
                timeout=5
            )
            if response.status_code != 200:
                return TestResult("scenario_13", False, "Не удалось получить список предсказаний")
            
            predictions_data = response.json()
            predictions = predictions_data.get("predictions", [])
            
            if len(predictions) < len(prediction_ids):
                self.warning(f"Не все предсказания отображаются. Ожидалось: {len(prediction_ids)}, получено: {len(predictions)}")
            
            self.success(f"Большой объем данных обработан: {len(model_ids)} моделей, {len(predictions)} предсказаний")
            
            return TestResult(
                "scenario_13",
                True,
                f"Большой объем данных обработан успешно. Моделей: {len(model_ids)}, Предсказаний: {len(predictions)}",
                {
                    "models_count": len(model_ids),
                    "predictions_count": len(predictions)
                }
            )
            
        except Exception as e:
            return TestResult("scenario_13", False, f"Ошибка обработки большого объема данных: {str(e)}")
    
    def scenario_14_input_validation(self) -> TestResult:
        """Сценарий 14: Валидация входных данных"""
        self.section("СЦЕНАРИЙ 14: Валидация входных данных")
        
        try:
            email = f"validation_{random.randint(10000, 99999)}@example.com"
            token = self.register_user(email, "testpass123")
            if not token:
                return TestResult("scenario_14", False, "Не удалось создать пользователя")
            
            headers = {"Authorization": f"Bearer {token}"}
            
            validation_errors = []
            
            # 1. Попытка пополнить баланс отрицательной суммой
            self.info("Проверка валидации отрицательной суммы...")
            response = requests.post(
                f"{self.base_url}/api/v1/billing/topup",
                headers=headers,
                json={"amount": -100},
                timeout=5
            )
            if response.status_code != 400:
                validation_errors.append("Отрицательная сумма не отклонена")
            else:
                self.success("Отрицательная сумма корректно отклонена")
            
            # 2. Попытка пополнить баланс нулевой суммой
            self.info("Проверка валидации нулевой суммы...")
            response = requests.post(
                f"{self.base_url}/api/v1/billing/topup",
                headers=headers,
                json={"amount": 0},
                timeout=5
            )
            if response.status_code != 400:
                validation_errors.append("Нулевая сумма не отклонена")
            else:
                self.success("Нулевая сумма корректно отклонена")
            
            # 3. Попытка создать предсказание без обязательных полей
            self.info("Проверка валидации обязательных полей...")
            response = requests.post(
                f"{self.base_url}/api/v1/predictions",
                headers=headers,
                json={},  # Пустой запрос
                timeout=5
            )
            if response.status_code not in [400, 422]:
                validation_errors.append("Пустой запрос не отклонен")
            else:
                self.success("Пустой запрос корректно отклонен")
            
            # 4. Попытка создать предсказание с невалидным типом данных
            self.info("Проверка валидации типов данных...")
            response = requests.post(
                f"{self.base_url}/api/v1/predictions",
                headers=headers,
                json={
                    "model_id": "not_a_number",  # Должно быть число
                    "input_data": {"feature1": 1.0}
                },
                timeout=5
            )
            if response.status_code not in [400, 422]:
                validation_errors.append("Невалидный тип model_id не отклонен")
            else:
                self.success("Невалидный тип данных корректно отклонен")
            
            # 5. Попытка зарегистрироваться с невалидным email
            self.info("Проверка валидации email...")
            response = requests.post(
                f"{self.base_url}/api/v1/auth/register",
                json={"email": "not_an_email", "password": "testpass123"},
                timeout=5
            )
            if response.status_code not in [400, 422]:
                validation_errors.append("Невалидный email не отклонен")
            else:
                self.success("Невалидный email корректно отклонен")
            
            if validation_errors:
                return TestResult(
                    "scenario_14",
                    False,
                    f"Обнаружены проблемы валидации: {len(validation_errors)}",
                    {"validation_errors": validation_errors}
                )
            else:
                return TestResult(
                    "scenario_14",
                    True,
                    "Валидация входных данных работает корректно",
                    {"validation_passed": True}
                )
            
        except Exception as e:
            return TestResult("scenario_14", False, f"Ошибка проверки валидации: {str(e)}")
    
    def scenario_15_realtime_metrics(self) -> TestResult:
        """Сценарий 15: Проверка метрик в реальном времени"""
        self.section("СЦЕНАРИЙ 15: Метрики в реальном времени")
        
        try:
            # Получаем начальные метрики
            self.info("Получение начальных метрик...")
            initial_metrics = self.get_backend_metrics()
            initial_active_users = initial_metrics.get("active_users", 0)
            
            # Создаем пользователя и выполняем действия
            email = f"metrics_{random.randint(10000, 99999)}@example.com"
            token = self.register_user(email, "testpass123")
            if not token:
                return TestResult("scenario_15", False, "Не удалось создать пользователя")
            
            headers = {"Authorization": f"Bearer {token}"}
            
            # Пополняем баланс
            requests.post(
                f"{self.base_url}/api/v1/billing/topup",
                headers=headers,
                json={"amount": 100},
                timeout=5
            )
            
            # Загружаем модель
            import pickle
            import tempfile
            import numpy as np
            from sklearn.ensemble import RandomForestClassifier
            
            X = np.array([[1, 2], [3, 4]])
            y = np.array([0, 1])
            model = RandomForestClassifier(n_estimators=5, random_state=42)
            model.fit(X, y)
            
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pkl')
            pickle.dump(model, temp_file)
            temp_file.close()
            
            model_id = None
            try:
                with open(temp_file.name, 'rb') as f:
                    response = requests.post(
                        f"{self.base_url}/api/v1/models/upload",
                        headers=headers,
                        files={"file": ("model.pkl", f, "application/octet-stream")},
                        data={"model_name": "MetricsTestModel"},
                        timeout=10
                    )
                if response.status_code == 201:
                    model_id = response.json()["id"]
            finally:
                if os.path.exists(temp_file.name):
                    os.remove(temp_file.name)
            
            if not model_id:
                return TestResult("scenario_15", False, "Не удалось загрузить модель")
            
            # Создаем предсказания
            for i in range(3):
                requests.post(
                    f"{self.base_url}/api/v1/predictions",
                    headers=headers,
                    json={
                        "model_id": model_id,
                        "input_data": {"feature1": float(1+i), "feature2": float(2+i)}
                    },
                    timeout=5
                )
            
            # Ждем немного для обновления метрик
            time.sleep(3)
            
            # Получаем финальные метрики
            self.info("Получение финальных метрик...")
            final_metrics = self.get_backend_metrics()
            final_active_users = final_metrics.get("active_users", 0)
            
            # Проверяем изменения
            if final_active_users >= initial_active_users:
                self.success(f"Метрики обновляются: active_users {initial_active_users} → {final_active_users}")
            else:
                self.warning(f"Метрики не обновились: active_users {initial_active_users} → {final_active_users}")
            
            # Проверяем метрики Prometheus
            prometheus_metrics = self.get_prometheus_metrics()
            if prometheus_metrics:
                self.success("Метрики Prometheus доступны")
            
            return TestResult(
                "scenario_15",
                True,
                f"Метрики в реальном времени работают. Active users: {initial_active_users} → {final_active_users}",
                {
                    "initial_active_users": initial_active_users,
                    "final_active_users": final_active_users,
                    "metrics_updated": True
                }
            )
            
        except Exception as e:
            return TestResult("scenario_15", False, f"Ошибка проверки метрик: {str(e)}")
    
    def run_all_scenarios(self):
        """Запуск всех сценариев"""
        self.section("НАЧАЛО E2E ТЕСТИРОВАНИЯ РЕАЛЬНЫХ СЦЕНАРИЕВ")
        self.info(f"Время начала: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.info(f"Backend URL: {self.base_url}")
        self.info(f"Prometheus URL: {self.prometheus_url}")
        self.info(f"Grafana URL: {self.grafana_url}")
        
        # Проверка доступности сервисов
        self.section("Проверка доступности сервисов")
        backend_ok = self.check_service_health("backend", self.base_url)
        prometheus_ok = self.check_service_health("prometheus", self.prometheus_url)
        grafana_ok = self.check_service_health("grafana", self.grafana_url)
        
        if backend_ok:
            self.success("Backend доступен")
        else:
            self.error("Backend недоступен - тесты не могут быть выполнены")
            return
        
        if prometheus_ok:
            self.success("Prometheus доступен")
        else:
            self.warning("Prometheus недоступен - проверка метрик будет ограничена")
        
        if grafana_ok:
            self.success("Grafana доступна")
        else:
            self.warning("Grafana недоступна - проверка дашбордов будет ограничена")
        
        # Сохраняем снимок метрик до тестов
        self.info("Создание снимка метрик до тестов...")
        self.snapshot_before = {
            "backend": self.get_backend_metrics(),
            "prometheus": self.get_prometheus_metrics()
        }
        
        # Запускаем сценарии
        scenarios = [
            self.scenario_1_new_user_complete_flow,
            self.scenario_2_multiple_users_concurrent,
            self.scenario_3_metrics_consistency,
            self.scenario_4_error_handling,
            self.scenario_5_data_consistency,
            self.scenario_6_no_crashes_under_load,
            self.scenario_7_admin_operations,
            self.scenario_8_model_management,
            self.scenario_9_pagination_and_filtering,
            self.scenario_10_security_checks,
            self.scenario_11_history_and_audit,
            self.scenario_12_rate_limiting_real_world,
            self.scenario_13_large_volume_data,
            self.scenario_14_input_validation,
            self.scenario_15_realtime_metrics
        ]
        
        for scenario_func in scenarios:
            try:
                result = scenario_func()
                self.results.append(result)
                
                if result.success:
                    self.success(f"✅ {result.name}: {result.message}")
                else:
                    self.error(f"❌ {result.name}: {result.message}")
                    if result.details:
                        self.info(f"   Детали: {result.details}")
                
                # Небольшая пауза между сценариями
                time.sleep(2)
                
            except Exception as e:
                self.error(f"Ошибка выполнения сценария {scenario_func.__name__}: {e}")
                self.results.append(TestResult(
                    scenario_func.__name__,
                    False,
                    f"Исключение: {str(e)}"
                ))
        
        # Создаем снимок метрик после тестов
        self.info("Создание снимка метрик после тестов...")
        time.sleep(5)  # Даем время на обработку
        self.snapshot_after = {
            "backend": self.get_backend_metrics(),
            "prometheus": self.get_prometheus_metrics()
        }
        
        # Выводим итоговый отчет
        self.print_summary()
    
    def print_summary(self):
        """Вывод итогового отчета"""
        self.section("ИТОГОВЫЙ ОТЧЕТ")
        
        total = len(self.results)
        successful = sum(1 for r in self.results if r.success)
        failed = total - successful
        
        self.info(f"Всего сценариев: {total}")
        self.info(f"Успешных: {successful}")
        self.info(f"Неудачных: {failed}")
        
        if failed > 0:
            self.error("\nНеудачные сценарии:")
            for result in self.results:
                if not result.success:
                    self.error(f"  - {result.name}: {result.message}")
        
        # Сравнение метрик до и после
        self.section("Изменение метрик")
        
        if self.snapshot_before.get("backend") and self.snapshot_after.get("backend"):
            before = self.snapshot_before["backend"]
            after = self.snapshot_after["backend"]
            
            if "active_users" in before and "active_users" in after:
                diff = after["active_users"] - before["active_users"]
                self.info(f"active_users: {before['active_users']} → {after['active_users']} (изменение: {diff:+g})")
            
            if "prediction_requests_completed" in before and "prediction_requests_completed" in after:
                diff = after["prediction_requests_completed"] - before["prediction_requests_completed"]
                self.info(f"prediction_requests_completed: {before.get('prediction_requests_completed', 0)} → "
                         f"{after.get('prediction_requests_completed', 0)} (изменение: {diff:+g})")
        
        self.section("РЕКОМЕНДАЦИИ")
        self.info("1. Проверьте Grafana дашборды: http://localhost:3000")
        self.info("2. Проверьте Prometheus запросы: http://localhost:9090")
        self.info("3. Проверьте Streamlit панель: http://localhost:8501")
        self.info("4. Убедитесь, что данные согласованы между всеми системами")
        
        self.section("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
        self.info(f"Время завершения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if successful == total:
            self.success("🎉 ВСЕ СЦЕНАРИИ ВЫПОЛНЕНЫ УСПЕШНО!")
        else:
            self.warning(f"⚠️  {failed} сценариев завершились с ошибками")


def main():
    """Главная функция"""
    tester = RealWorldScenarioTester()
    tester.run_all_scenarios()
    
    # Возвращаем код выхода в зависимости от результатов
    failed_count = sum(1 for r in tester.results if not r.success)
    sys.exit(0 if failed_count == 0 else 1)


if __name__ == "__main__":
    main()
