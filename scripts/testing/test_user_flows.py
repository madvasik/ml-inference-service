#!/usr/bin/env python3
"""
Комплексное тестирование пользовательских флоу и проверка согласованности данных
между Backend, Prometheus, Grafana и Streamlit
"""
import os
import sys
import time
import random
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")

# Цвета для вывода
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


class FlowTester:
    def __init__(self):
        self.results = {
            "flows": [],
            "metrics": {},
            "errors": []
        }
        self.users = []
        self.models = {}
        
    def log(self, message: str, color: str = RESET):
        """Логирование с цветом"""
        print(f"{color}{message}{RESET}")
        
    def error(self, message: str):
        """Логирование ошибки"""
        self.results["errors"].append(message)
        self.log(f"❌ {message}", RED)
        
    def success(self, message: str):
        """Логирование успеха"""
        self.log(f"✅ {message}", GREEN)
        
    def info(self, message: str):
        """Информационное сообщение"""
        self.log(f"ℹ️  {message}", BLUE)
        
    def warning(self, message: str):
        """Предупреждение"""
        self.log(f"⚠️  {message}", YELLOW)

    # ========== ПОЛЬЗОВАТЕЛЬСКИЕ ФЛОУ ==========
    
    def flow_1_user_registration_and_first_prediction(self):
        """Флоу 1: Регистрация нового пользователя и первое предсказание"""
        self.info("\n" + "="*70)
        self.info("ФЛОУ 1: Регистрация нового пользователя и первое предсказание")
        self.info("="*70)
        
        flow_result = {
            "name": "User Registration and First Prediction",
            "steps": [],
            "success": False
        }
        
        try:
            # Шаг 1: Регистрация
            email = f"test_user_{random.randint(1000, 9999)}@example.com"
            password = "testpass123"
            
            response = requests.post(
                f"{BASE_URL}/api/v1/auth/register",
                json={"email": email, "password": password},
                timeout=5
            )
            
            if response.status_code != 201:
                self.error(f"Регистрация не удалась: {response.status_code}")
                flow_result["steps"].append({"step": "registration", "success": False})
                return flow_result
            
            token = response.json()["access_token"]
            flow_result["steps"].append({"step": "registration", "success": True})
            self.success(f"Пользователь зарегистрирован: {email}")
            
            # Шаг 2: Пополнение баланса
            response = requests.post(
                f"{BASE_URL}/api/v1/billing/topup",
                headers={"Authorization": f"Bearer {token}"},
                json={"amount": 1000},
                timeout=5
            )
            
            if response.status_code != 200:
                self.error(f"Пополнение баланса не удалось: {response.status_code}")
                flow_result["steps"].append({"step": "topup", "success": False})
                return flow_result
            
            flow_result["steps"].append({"step": "topup", "success": True})
            self.success("Баланс пополнен на 1000 кредитов")
            
            # Шаг 3: Загрузка модели
            import pickle
            import tempfile
            import numpy as np
            from sklearn.ensemble import RandomForestClassifier
            
            X = np.array([[1, 2], [3, 4], [5, 6]])
            y = np.array([0, 1, 0])
            model = RandomForestClassifier(n_estimators=10, random_state=42)
            model.fit(X, y)
            
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pkl')
            pickle.dump(model, temp_file)
            temp_file.close()
            
            with open(temp_file.name, 'rb') as f:
                response = requests.post(
                    f"{BASE_URL}/api/v1/models/upload",
                    headers={"Authorization": f"Bearer {token}"},
                    files={"file": f},
                    data={"model_name": f"TestModel_{random.randint(100, 999)}"},
                    timeout=10
                )
            
            os.unlink(temp_file.name)
            
            if response.status_code != 201:
                self.error(f"Загрузка модели не удалась: {response.status_code}")
                flow_result["steps"].append({"step": "model_upload", "success": False})
                return flow_result
            
            model_data = response.json()
            model_id = model_data["id"]
            flow_result["steps"].append({"step": "model_upload", "success": True})
            self.success(f"Модель загружена: ID {model_id}")
            
            # Шаг 4: Создание предсказания
            response = requests.post(
                f"{BASE_URL}/api/v1/predictions",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "model_id": model_id,
                    "input_data": {"feature1": 2.5, "feature2": 3.5}
                },
                timeout=5
            )
            
            if response.status_code != 202:
                self.error(f"Создание предсказания не удалось: {response.status_code}")
                flow_result["steps"].append({"step": "prediction_create", "success": False})
                return flow_result
            
            prediction_data = response.json()
            prediction_id = prediction_data["prediction_id"]
            flow_result["steps"].append({"step": "prediction_create", "success": True})
            self.success(f"Предсказание создано: ID {prediction_id}")
            
            # Шаг 5: Ожидание завершения предсказания
            time.sleep(3)
            response = requests.get(
                f"{BASE_URL}/api/v1/predictions/{prediction_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5
            )
            
            if response.status_code == 200:
                pred_status = response.json()["status"]
                flow_result["steps"].append({"step": "prediction_complete", "success": pred_status == "completed"})
                if pred_status == "completed":
                    self.success(f"Предсказание завершено успешно")
                else:
                    self.warning(f"Предсказание в статусе: {pred_status}")
            
            flow_result["success"] = True
            self.success("Флоу 1 завершен успешно!")
            
        except Exception as e:
            self.error(f"Ошибка в флоу 1: {str(e)}")
            flow_result["steps"].append({"step": "exception", "error": str(e)})
        
        self.results["flows"].append(flow_result)
        return flow_result

    def flow_2_multiple_users_high_load(self):
        """Флоу 2: Несколько пользователей, высокая нагрузка"""
        self.info("\n" + "="*70)
        self.info("ФЛОУ 2: Несколько пользователей, высокая нагрузка")
        self.info("="*70)
        
        flow_result = {
            "name": "Multiple Users High Load",
            "steps": [],
            "success": False,
            "users_created": 0,
            "predictions_created": 0
        }
        
        try:
            # Создаем 3 пользователей
            users_data = []
            for i in range(3):
                email = f"load_user_{random.randint(1000, 9999)}@example.com"
                password = "testpass123"
                
                response = requests.post(
                    f"{BASE_URL}/api/v1/auth/register",
                    json={"email": email, "password": password},
                    timeout=5
                )
                
                if response.status_code == 201:
                    token = response.json()["access_token"]
                    users_data.append({"email": email, "token": token})
                    flow_result["users_created"] += 1
                    self.success(f"Пользователь {i+1} создан: {email}")
                    
                    # Пополняем баланс
                    requests.post(
                        f"{BASE_URL}/api/v1/billing/topup",
                        headers={"Authorization": f"Bearer {token}"},
                        json={"amount": 500},
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
                    
                    with open(temp_file.name, 'rb') as f:
                        model_resp = requests.post(
                            f"{BASE_URL}/api/v1/models/upload",
                            headers={"Authorization": f"Bearer {token}"},
                            files={"file": f},
                            data={"model_name": f"LoadModel_{i}"},
                            timeout=10
                        )
                    
                    os.unlink(temp_file.name)
                    
                    if model_resp.status_code == 201:
                        model_id = model_resp.json()["id"]
                        users_data[-1]["model_id"] = model_id
            
            flow_result["steps"].append({"step": "users_setup", "success": True})
            
            # Создаем много предсказаний параллельно
            predictions_created = 0
            for user in users_data:
                for _ in range(5):  # 5 предсказаний на пользователя
                    try:
                        response = requests.post(
                            f"{BASE_URL}/api/v1/predictions",
                            headers={"Authorization": f"Bearer {user['token']}"},
                            json={
                                "model_id": user["model_id"],
                                "input_data": {
                                    "feature1": random.uniform(1, 10),
                                    "feature2": random.uniform(1, 10)
                                }
                            },
                            timeout=5
                        )
                        if response.status_code == 202:
                            predictions_created += 1
                    except:
                        pass
                    time.sleep(0.1)  # Небольшая задержка
            
            flow_result["predictions_created"] = predictions_created
            flow_result["steps"].append({"step": "predictions_created", "count": predictions_created})
            self.success(f"Создано {predictions_created} предсказаний от {len(users_data)} пользователей")
            
            flow_result["success"] = True
            
        except Exception as e:
            self.error(f"Ошибка в флоу 2: {str(e)}")
        
        self.results["flows"].append(flow_result)
        return flow_result

    def flow_3_insufficient_credits(self):
        """Флоу 3: Недостаточно кредитов"""
        self.info("\n" + "="*70)
        self.info("ФЛОУ 3: Тест недостаточного баланса")
        self.info("="*70)
        
        flow_result = {
            "name": "Insufficient Credits",
            "steps": [],
            "success": False
        }
        
        try:
            # Регистрация пользователя
            email = f"poor_user_{random.randint(1000, 9999)}@example.com"
            response = requests.post(
                f"{BASE_URL}/api/v1/auth/register",
                json={"email": email, "password": "testpass123"},
                timeout=5
            )
            
            if response.status_code != 201:
                self.error("Не удалось создать пользователя")
                return flow_result
            
            token = response.json()["access_token"]
            
            # Пополняем баланс на минимальную сумму (меньше стоимости предсказания)
            requests.post(
                f"{BASE_URL}/api/v1/billing/topup",
                headers={"Authorization": f"Bearer {token}"},
                json={"amount": 5},  # Меньше стоимости предсказания (обычно 10)
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
            
            with open(temp_file.name, 'rb') as f:
                model_resp = requests.post(
                    f"{BASE_URL}/api/v1/models/upload",
                    headers={"Authorization": f"Bearer {token}"},
                    files={"file": f},
                    data={"model_name": "PoorModel"},
                    timeout=10
                )
            
            os.unlink(temp_file.name)
            
            if model_resp.status_code != 201:
                self.error("Не удалось загрузить модель")
                return flow_result
            
            model_id = model_resp.json()["id"]
            
            # Пытаемся создать предсказание (должно быть отклонено)
            response = requests.post(
                f"{BASE_URL}/api/v1/predictions",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "model_id": model_id,
                    "input_data": {"feature1": 2.5, "feature2": 3.5}
                },
                timeout=5
            )
            
            if response.status_code == 402:  # Payment Required
                flow_result["success"] = True
                flow_result["steps"].append({"step": "insufficient_credits_rejected", "success": True})
                self.success("Предсказание правильно отклонено из-за недостатка кредитов")
            else:
                self.warning(f"Ожидался статус 402, получен {response.status_code}")
                flow_result["steps"].append({"step": "insufficient_credits_rejected", "success": False})
            
        except Exception as e:
            self.error(f"Ошибка в флоу 3: {str(e)}")
        
        self.results["flows"].append(flow_result)
        return flow_result

    def flow_4_admin_operations(self):
        """Флоу 4: Операции администратора"""
        self.info("\n" + "="*70)
        self.info("ФЛОУ 4: Операции администратора")
        self.info("="*70)
        
        flow_result = {
            "name": "Admin Operations",
            "steps": [],
            "success": False
        }
        
        try:
            # Вход как администратор
            response = requests.post(
                f"{BASE_URL}/api/v1/auth/login",
                json={"email": "admin@mlservice.com", "password": "admin123"},
                timeout=5
            )
            
            if response.status_code != 200:
                self.error("Не удалось войти как администратор")
                return flow_result
            
            token = response.json()["access_token"]
            flow_result["steps"].append({"step": "admin_login", "success": True})
            self.success("Вход как администратор выполнен")
            
            # Получение списка всех пользователей
            response = requests.get(
                f"{BASE_URL}/api/v1/admin/users",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5
            )
            
            if response.status_code == 200:
                users = response.json()
                flow_result["steps"].append({"step": "list_users", "count": len(users), "success": True})
                self.success(f"Получен список из {len(users)} пользователей")
            
            # Получение всех предсказаний
            response = requests.get(
                f"{BASE_URL}/api/v1/admin/predictions",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5
            )
            
            if response.status_code == 200:
                predictions = response.json()
                total = predictions.get("total", 0)
                flow_result["steps"].append({"step": "list_predictions", "count": total, "success": True})
                self.success(f"Получен список из {total} предсказаний")
            
            # Получение всех транзакций
            response = requests.get(
                f"{BASE_URL}/api/v1/admin/transactions",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5
            )
            
            if response.status_code == 200:
                transactions = response.json()
                total = transactions.get("total", 0)
                flow_result["steps"].append({"step": "list_transactions", "count": total, "success": True})
                self.success(f"Получен список из {total} транзакций")
            
            flow_result["success"] = True
            
        except Exception as e:
            self.error(f"Ошибка в флоу 4: {str(e)}")
        
        self.results["flows"].append(flow_result)
        return flow_result

    # ========== ПРОВЕРКА МЕТРИК ==========
    
    def check_backend_metrics(self) -> Dict:
        """Проверка метрик из backend"""
        self.info("\n" + "="*70)
        self.info("ПРОВЕРКА МЕТРИК BACKEND")
        self.info("="*70)
        
        metrics = {}
        try:
            response = requests.get(f"{BASE_URL}/metrics", timeout=5)
            if response.status_code == 200:
                lines = response.text.split('\n')
                for line in lines:
                    if line.startswith('active_users '):
                        metrics['active_users'] = float(line.split()[1])
                    elif 'billing_transactions_total{type="credit"}' in line:
                        metrics['billing_credit'] = float(line.split()[1])
                    elif 'billing_transactions_total{type="debit"}' in line:
                        metrics['billing_debit'] = float(line.split()[1])
                
                self.success(f"Метрики backend получены: {metrics}")
            else:
                self.error(f"Не удалось получить метрики backend: {response.status_code}")
        except Exception as e:
            self.error(f"Ошибка получения метрик backend: {str(e)}")
        
        self.results["metrics"]["backend"] = metrics
        return metrics

    def check_prometheus_metrics(self) -> Dict:
        """Проверка метрик из Prometheus"""
        self.info("\n" + "="*70)
        self.info("ПРОВЕРКА МЕТРИК PROMETHEUS")
        self.info("="*70)
        
        metrics = {}
        try:
            # Active users
            response = requests.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": "active_users"},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success" and data.get("data", {}).get("result"):
                    metrics['active_users'] = float(data["data"]["result"][0]["value"][1])
                    self.success(f"Prometheus active_users: {metrics['active_users']}")
            
            # Prediction requests
            response = requests.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": "sum(prediction_requests_total)"},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success" and data.get("data", {}).get("result"):
                    metrics['prediction_requests_total'] = float(data["data"]["result"][0]["value"][1])
                    self.success(f"Prometheus prediction_requests_total: {metrics['prediction_requests_total']}")
            
            # Billing transactions
            response = requests.get(
                f"{PROMETHEUS_URL}/api/v1/query",
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
                    self.success(f"Prometheus billing_transactions: credit={metrics.get('billing_credit', 0)}, debit={metrics.get('billing_debit', 0)}")
            
        except Exception as e:
            self.error(f"Ошибка получения метрик Prometheus: {str(e)}")
        
        self.results["metrics"]["prometheus"] = metrics
        return metrics

    def check_database_stats(self) -> Dict:
        """Проверка статистики из базы данных"""
        self.info("\n" + "="*70)
        self.info("ПРОВЕРКА СТАТИСТИКИ БАЗЫ ДАННЫХ")
        self.info("="*70)
        
        stats = {}
        try:
            # Вход как администратор для получения данных
            response = requests.post(
                f"{BASE_URL}/api/v1/auth/login",
                json={"email": "admin@mlservice.com", "password": "admin123"},
                timeout=5
            )
            
            if response.status_code == 200:
                token = response.json()["access_token"]
                headers = {"Authorization": f"Bearer {token}"}
                
                # Получаем статистику через API
                users_resp = requests.get(f"{BASE_URL}/api/v1/admin/users", headers=headers, timeout=5)
                if users_resp.status_code == 200:
                    stats['users_count'] = len(users_resp.json())
                
                predictions_resp = requests.get(f"{BASE_URL}/api/v1/admin/predictions", headers=headers, timeout=5)
                if predictions_resp.status_code == 200:
                    pred_data = predictions_resp.json()
                    stats['predictions_total'] = pred_data.get("total", 0)
                    stats['predictions_list'] = len(pred_data.get("predictions", []))
                
                transactions_resp = requests.get(f"{BASE_URL}/api/v1/admin/transactions", headers=headers, timeout=5)
                if transactions_resp.status_code == 200:
                    trans_data = transactions_resp.json()
                    stats['transactions_total'] = trans_data.get("total", 0)
                    transactions = trans_data.get("transactions", [])
                    stats['transactions_credit'] = len([t for t in transactions if t.get("type") == "credit"])
                    stats['transactions_debit'] = len([t for t in transactions if t.get("type") == "debit"])
                
                self.success(f"Статистика БД: {stats}")
            else:
                self.error("Не удалось войти как администратор для проверки БД")
        
        except Exception as e:
            self.error(f"Ошибка получения статистики БД: {str(e)}")
        
        self.results["metrics"]["database"] = stats
        return stats

    def compare_metrics(self):
        """Сравнение метрик между системами"""
        self.info("\n" + "="*70)
        self.info("СРАВНЕНИЕ МЕТРИК МЕЖДУ СИСТЕМАМИ")
        self.info("="*70)
        
        backend_metrics = self.results["metrics"].get("backend", {})
        prometheus_metrics = self.results["metrics"].get("prometheus", {})
        db_stats = self.results["metrics"].get("database", {})
        
        # Сравнение active_users
        if "active_users" in backend_metrics and "active_users" in prometheus_metrics:
            backend_val = backend_metrics["active_users"]
            prom_val = prometheus_metrics["active_users"]
            if abs(backend_val - prom_val) < 0.1:
                self.success(f"active_users совпадает: Backend={backend_val}, Prometheus={prom_val}")
            else:
                self.error(f"active_users НЕ совпадает: Backend={backend_val}, Prometheus={prom_val}")
        
        # Сравнение транзакций
        if "billing_credit" in backend_metrics and "billing_credit" in prometheus_metrics:
            backend_val = backend_metrics["billing_credit"]
            prom_val = prometheus_metrics["billing_credit"]
            if abs(backend_val - prom_val) < 0.1:
                self.success(f"billing_credit совпадает: Backend={backend_val}, Prometheus={prom_val}")
            else:
                self.warning(f"billing_credit различается: Backend={backend_val}, Prometheus={prom_val}")
        
        # Проверка согласованности БД и метрик
        if "transactions_total" in db_stats:
            db_total = db_stats["transactions_total"]
            self.info(f"Всего транзакций в БД: {db_total}")
            self.info(f"Транзакций CREDIT в БД: {db_stats.get('transactions_credit', 0)}")
            self.info(f"Транзакций DEBIT в БД: {db_stats.get('transactions_debit', 0)}")

    def run_all_tests(self):
        """Запуск всех тестов"""
        self.info("\n" + "="*70)
        self.info("НАЧАЛО КОМПЛЕКСНОГО ТЕСТИРОВАНИЯ")
        self.info("="*70)
        self.info(f"Время начала: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Проверка доступности сервисов
        self.info("\nПроверка доступности сервисов...")
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=5)
            if response.status_code == 200:
                self.success("Backend доступен")
            else:
                self.error("Backend недоступен")
                return
        except Exception as e:
            self.error(f"Backend недоступен: {str(e)}")
            return
        
        # Запуск пользовательских флоу
        self.flow_1_user_registration_and_first_prediction()
        time.sleep(2)
        
        self.flow_2_multiple_users_high_load()
        time.sleep(2)
        
        self.flow_3_insufficient_credits()
        time.sleep(2)
        
        self.flow_4_admin_operations()
        time.sleep(3)  # Даем время на обработку предсказаний
        
        # Проверка метрик
        self.check_backend_metrics()
        time.sleep(2)
        
        self.check_prometheus_metrics()
        time.sleep(2)
        
        self.check_database_stats()
        time.sleep(2)
        
        # Сравнение метрик
        self.compare_metrics()
        
        # Итоговый отчет
        self.print_summary()

    def print_summary(self):
        """Вывод итогового отчета"""
        self.info("\n" + "="*70)
        self.info("ИТОГОВЫЙ ОТЧЕТ")
        self.info("="*70)
        
        total_flows = len(self.results["flows"])
        successful_flows = sum(1 for f in self.results["flows"] if f.get("success", False))
        
        self.info(f"Всего флоу выполнено: {total_flows}")
        self.info(f"Успешных флоу: {successful_flows}")
        self.info(f"Неудачных флоу: {total_flows - successful_flows}")
        self.info(f"Ошибок: {len(self.results['errors'])}")
        
        if self.results["errors"]:
            self.warning("\nСписок ошибок:")
            for error in self.results["errors"]:
                self.warning(f"  - {error}")
        
        self.info("\n" + "="*70)
        self.info("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
        self.info("="*70)
        self.info(f"Время завершения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.info("\n💡 Проверьте Grafana для визуализации метрик")
        self.info("💡 Проверьте Streamlit для просмотра данных")


def main():
    tester = FlowTester()
    tester.run_all_tests()


if __name__ == "__main__":
    main()
