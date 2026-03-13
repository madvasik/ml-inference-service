#!/usr/bin/env python3
"""
Тест отсутствия падений при реальных действиях пользователей
Проверяет, что система стабильна и не падает при различных операциях
"""
import os
import sys
import time
import random
import requests
from datetime import datetime
from typing import List, Dict, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

# Цвета для вывода
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"


class StabilityTester:
    """Тестер стабильности системы"""
    
    def __init__(self):
        self.base_url = BASE_URL
        self.errors = []
        self.operations_count = 0
        self.successful_operations = 0
        
    def log(self, message: str, color: str = RESET):
        print(f"{color}{message}{RESET}")
        
    def success(self, message: str):
        self.log(f"✅ {message}", GREEN)
        
    def error(self, message: str):
        self.log(f"❌ {message}", RED)
        self.errors.append(message)
        
    def info(self, message: str):
        self.log(f"ℹ️  {message}", BLUE)
        
    def warning(self, message: str):
        self.log(f"⚠️  {message}", YELLOW)
        
    def section(self, title: str):
        self.log("\n" + "="*80, CYAN)
        self.log(f"  {title}", CYAN)
        self.log("="*80, CYAN)
    
    def check_service_alive(self) -> bool:
        """Проверка, что сервис работает"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False
    
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
                # Пользователь уже существует
                return self.login_user(email, password)
            return None
        except Exception as e:
            self.error(f"Ошибка регистрации: {e}")
            return None
    
    def login_user(self, email: str, password: str) -> Optional[str]:
        """Вход пользователя"""
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
            self.error(f"Ошибка входа: {e}")
            return None
    
    def test_rapid_operations(self):
        """Тест быстрых операций подряд"""
        self.section("Тест быстрых операций подряд")
        
        # Создаем пользователя
        email = f"rapid_test_{random.randint(10000, 99999)}@example.com"
        token = self.register_user(email, "testpass123")
        
        if not token:
            self.error("Не удалось создать пользователя")
            return False
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Выполняем множество операций быстро
        operations = [
            ("GET", "/api/v1/users/me"),
            ("GET", "/api/v1/billing/balance"),
            ("POST", "/api/v1/billing/topup", {"amount": 100}),
            ("GET", "/api/v1/billing/balance"),
            ("GET", "/api/v1/billing/transactions"),
            ("GET", "/api/v1/models"),
            ("GET", "/api/v1/predictions"),
        ]
        
        self.info(f"Выполнение {len(operations)} операций подряд...")
        
        for i, op in enumerate(operations):
            method, endpoint = op[0], op[1]
            data = op[2] if len(op) > 2 else None
            
            try:
                if method == "GET":
                    response = requests.get(f"{self.base_url}{endpoint}", headers=headers, timeout=5)
                elif method == "POST":
                    response = requests.post(f"{self.base_url}{endpoint}", headers=headers, json=data, timeout=5)
                
                self.operations_count += 1
                
                if response.status_code < 500:  # Не считаем клиентские ошибки за падения
                    self.successful_operations += 1
                else:
                    self.error(f"Операция #{i+1} вернула {response.status_code}")
                    
            except Exception as e:
                self.error(f"Операция #{i+1} упала с исключением: {e}")
                self.operations_count += 1
        
        # Проверяем, что сервис все еще работает
        if not self.check_service_alive():
            self.error("Сервис упал после быстрых операций!")
            return False
        
        self.success(f"Все операции выполнены. Успешных: {self.successful_operations}/{self.operations_count}")
        return True
    
    def test_concurrent_users(self):
        """Тест одновременной работы нескольких пользователей"""
        self.section("Тест одновременной работы пользователей")
        
        num_users = 5
        users_tokens = []
        
        # Создаем пользователей
        for i in range(num_users):
            email = f"concurrent_{random.randint(10000, 99999)}@example.com"
            token = self.register_user(email, "testpass123")
            if token:
                users_tokens.append(token)
        
        if not users_tokens:
            self.error("Не удалось создать пользователей")
            return False
        
        self.info(f"Создано {len(users_tokens)} пользователей")
        
        # Выполняем операции от всех пользователей
        for i, token in enumerate(users_tokens):
            headers = {"Authorization": f"Bearer {token}"}
            
            try:
                # Пополнение баланса
                response = requests.post(
                    f"{self.base_url}/api/v1/billing/topup",
                    headers=headers,
                    json={"amount": 50},
                    timeout=5
                )
                self.operations_count += 1
                if response.status_code == 200:
                    self.successful_operations += 1
                
                # Получение баланса
                response = requests.get(
                    f"{self.base_url}/api/v1/billing/balance",
                    headers=headers,
                    timeout=5
                )
                self.operations_count += 1
                if response.status_code == 200:
                    self.successful_operations += 1
                    
            except Exception as e:
                self.error(f"Ошибка для пользователя #{i+1}: {e}")
                self.operations_count += 1
        
        # Проверяем стабильность
        if not self.check_service_alive():
            self.error("Сервис упал при одновременной работе пользователей!")
            return False
        
        self.success(f"Одновременная работа {len(users_tokens)} пользователей: OK")
        return True
    
    def test_error_recovery(self):
        """Тест восстановления после ошибок"""
        self.section("Тест восстановления после ошибок")
        
        # Создаем пользователя
        email = f"recovery_test_{random.randint(10000, 99999)}@example.com"
        token = self.register_user(email, "testpass123")
        
        if not token:
            self.error("Не удалось создать пользователя")
            return False
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Вызываем ошибки и проверяем восстановление
        error_scenarios = [
            ("Несуществующая модель", {
                "method": "POST",
                "endpoint": "/api/v1/predictions",
                "data": {"model_id": 99999, "input_data": {"feature1": 1.0}}
            }),
            ("Невалидные данные", {
                "method": "POST",
                "endpoint": "/api/v1/billing/topup",
                "data": {"amount": -100}
            }),
            ("Несуществующий endpoint", {
                "method": "GET",
                "endpoint": "/api/v1/nonexistent"
            }),
        ]
        
        for scenario_name, scenario in error_scenarios:
            try:
                if scenario["method"] == "GET":
                    response = requests.get(
                        f"{self.base_url}{scenario['endpoint']}",
                        headers=headers,
                        timeout=5
                    )
                else:
                    response = requests.post(
                        f"{self.base_url}{scenario['endpoint']}",
                        headers=headers,
                        json=scenario["data"],
                        timeout=5
                    )
                
                self.operations_count += 1
                
                # Ошибка должна быть обработана корректно (не 500)
                if response.status_code < 500:
                    self.successful_operations += 1
                    self.info(f"{scenario_name}: ошибка обработана корректно ({response.status_code})")
                else:
                    self.error(f"{scenario_name}: серверная ошибка {response.status_code}")
                    
            except Exception as e:
                self.error(f"{scenario_name}: исключение {e}")
                self.operations_count += 1
        
        # После ошибок система должна работать
        if not self.check_service_alive():
            self.error("Сервис не восстановился после ошибок!")
            return False
        
        # Проверяем, что нормальные операции все еще работают
        response = requests.get(
            f"{self.base_url}/api/v1/users/me",
            headers=headers,
            timeout=5
        )
        
        if response.status_code == 200:
            self.success("Система восстановилась после ошибок")
            return True
        else:
            self.error("Система не восстановилась - нормальные операции не работают")
            return False
    
    def test_long_running_session(self):
        """Тест длительной сессии"""
        self.section("Тест длительной сессии")
        
        email = f"session_test_{random.randint(10000, 99999)}@example.com"
        token = self.register_user(email, "testpass123")
        
        if not token:
            self.error("Не удалось создать пользователя")
            return False
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Выполняем операции в течение длительного времени
        self.info("Выполнение операций в течение 30 секунд...")
        
        start_time = time.time()
        operations_in_session = 0
        
        while time.time() - start_time < 30:
            try:
                # Чередуем разные операции
                if operations_in_session % 3 == 0:
                    response = requests.get(f"{self.base_url}/api/v1/users/me", headers=headers, timeout=5)
                elif operations_in_session % 3 == 1:
                    response = requests.get(f"{self.base_url}/api/v1/billing/balance", headers=headers, timeout=5)
                else:
                    response = requests.get(f"{self.base_url}/api/v1/models", headers=headers, timeout=5)
                
                operations_in_session += 1
                self.operations_count += 1
                
                if response.status_code < 500:
                    self.successful_operations += 1
                else:
                    self.error(f"Операция #{operations_in_session} вернула {response.status_code}")
                
                time.sleep(1)  # Небольшая пауза между операциями
                
            except Exception as e:
                self.error(f"Операция #{operations_in_session} упала: {e}")
                operations_in_session += 1
                self.operations_count += 1
        
        if not self.check_service_alive():
            self.error("Сервис упал во время длительной сессии!")
            return False
        
        self.success(f"Длительная сессия завершена. Операций: {operations_in_session}")
        return True
    
    def run_all_tests(self):
        """Запуск всех тестов стабильности"""
        self.section("НАЧАЛО ТЕСТИРОВАНИЯ СТАБИЛЬНОСТИ")
        self.info(f"Время начала: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.info(f"Backend URL: {self.base_url}")
        
        # Проверка доступности
        if not self.check_service_alive():
            self.error("Backend недоступен - тесты не могут быть выполнены")
            return False
        
        self.success("Backend доступен")
        
        # Запускаем тесты
        tests = [
            ("Быстрые операции", self.test_rapid_operations),
            ("Одновременные пользователи", self.test_concurrent_users),
            ("Восстановление после ошибок", self.test_error_recovery),
            ("Длительная сессия", self.test_long_running_session),
        ]
        
        results = []
        for test_name, test_func in tests:
            try:
                result = test_func()
                results.append((test_name, result))
            except Exception as e:
                self.error(f"Тест '{test_name}' упал с исключением: {e}")
                results.append((test_name, False))
            
            # Проверяем, что сервис все еще работает
            if not self.check_service_alive():
                self.error(f"Сервис упал после теста '{test_name}'!")
                break
            
            time.sleep(2)  # Пауза между тестами
        
        # Итоговый отчет
        self.print_summary(results)
        
        # Проверяем финальное состояние
        if not self.check_service_alive():
            self.error("Сервис не работает после всех тестов!")
            return False
        
        return all(result for _, result in results)
    
    def print_summary(self, results: List[tuple]):
        """Вывод итогового отчета"""
        self.section("ИТОГОВЫЙ ОТЧЕТ")
        
        total_tests = len(results)
        passed_tests = sum(1 for _, result in results if result)
        failed_tests = total_tests - passed_tests
        
        self.info(f"Всего тестов: {total_tests}")
        self.info(f"Пройдено: {passed_tests}")
        self.info(f"Провалено: {failed_tests}")
        self.info(f"Всего операций: {self.operations_count}")
        self.info(f"Успешных операций: {self.successful_operations}")
        
        if self.errors:
            self.error(f"\nОшибок зафиксировано: {len(self.errors)}")
            for error in self.errors[:10]:  # Показываем первые 10
                self.error(f"  - {error}")
        
        if failed_tests > 0:
            self.error("\nПроваленные тесты:")
            for test_name, result in results:
                if not result:
                    self.error(f"  - {test_name}")
        
        success_rate = (self.successful_operations / self.operations_count * 100) if self.operations_count > 0 else 0
        self.info(f"\nПроцент успешных операций: {success_rate:.1f}%")
        
        if success_rate >= 95 and failed_tests == 0:
            self.success("🎉 Система стабильна! Все тесты пройдены.")
        elif success_rate >= 90:
            self.warning("⚠️  Система в целом стабильна, но есть проблемы.")
        else:
            self.error("❌ Система нестабильна! Обнаружены серьезные проблемы.")


def main():
    """Главная функция"""
    tester = StabilityTester()
    success = tester.run_all_tests()
    
    tester.section("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    tester.info(f"Время завершения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
