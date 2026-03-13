#!/usr/bin/env python3
"""
Проверка согласованности данных между Backend, Prometheus и Grafana
для реальных пользовательских сценариев
"""
import os
import sys
import time
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")
GRAFANA_USER = os.getenv("GRAFANA_USER", "admin")
GRAFANA_PASSWORD = os.getenv("GRAFANA_PASSWORD", "admin")

# Цвета для вывода
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"


class GrafanaConsistencyChecker:
    """Проверка согласованности данных с Grafana"""
    
    def __init__(self):
        self.base_url = BASE_URL
        self.prometheus_url = PROMETHEUS_URL
        self.grafana_url = GRAFANA_URL
        self.grafana_auth = None
        self.inconsistencies = []
        
    def log(self, message: str, color: str = RESET):
        print(f"{color}{message}{RESET}")
        
    def success(self, message: str):
        self.log(f"✅ {message}", GREEN)
        
    def error(self, message: str):
        self.log(f"❌ {message}", RED)
        
    def info(self, message: str):
        self.log(f"ℹ️  {message}", BLUE)
        
    def warning(self, message: str):
        self.log(f"⚠️  {message}", YELLOW)
        
    def section(self, title: str):
        self.log("\n" + "="*80, CYAN)
        self.log(f"  {title}", CYAN)
        self.log("="*80, CYAN)
    
    def authenticate_grafana(self) -> bool:
        """Аутентификация в Grafana"""
        try:
            response = requests.post(
                f"{self.grafana_url}/api/auth/login",
                json={
                    "user": GRAFANA_USER,
                    "password": GRAFANA_PASSWORD
                },
                timeout=5
            )
            if response.status_code == 200:
                self.grafana_auth = response.headers.get("Set-Cookie", "")
                return True
            return False
        except Exception as e:
            self.warning(f"Не удалось аутентифицироваться в Grafana: {e}")
            return False
    
    def get_grafana_datasources(self) -> List[Dict]:
        """Получение списка datasources из Grafana"""
        try:
            headers = {"Cookie": self.grafana_auth} if self.grafana_auth else {}
            response = requests.get(
                f"{self.grafana_url}/api/datasources",
                headers=headers,
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            self.warning(f"Ошибка получения datasources: {e}")
            return []
    
    def check_prometheus_datasource(self) -> bool:
        """Проверка подключения Prometheus datasource в Grafana"""
        self.section("Проверка Prometheus Datasource в Grafana")
        
        if not self.authenticate_grafana():
            self.warning("Не удалось аутентифицироваться в Grafana - пропускаем проверку")
            return False
        
        datasources = self.get_grafana_datasources()
        prometheus_ds = None
        
        for ds in datasources:
            if ds.get("type") == "prometheus":
                prometheus_ds = ds
                break
        
        if not prometheus_ds:
            self.error("Prometheus datasource не найден в Grafana")
            return False
        
        self.success(f"Prometheus datasource найден: {prometheus_ds.get('name')}")
        
        # Проверяем доступность
        if prometheus_ds.get("access") == "proxy":
            self.info("Datasource использует proxy режим")
        
        # Проверяем URL
        ds_url = prometheus_ds.get("url", "")
        if "prometheus" in ds_url or "localhost:9090" in ds_url:
            self.success(f"URL datasource корректный: {ds_url}")
        else:
            self.warning(f"Необычный URL datasource: {ds_url}")
        
        return True
    
    def query_prometheus_via_grafana(self, query: str) -> Optional[float]:
        """Выполнение запроса к Prometheus через Grafana API"""
        try:
            headers = {"Cookie": self.grafana_auth} if self.grafana_auth else {}
            
            # Получаем ID Prometheus datasource
            datasources = self.get_grafana_datasources()
            prometheus_ds_id = None
            for ds in datasources:
                if ds.get("type") == "prometheus":
                    prometheus_ds_id = ds.get("id")
                    break
            
            if not prometheus_ds_id:
                return None
            
            # Выполняем запрос через Grafana API
            response = requests.post(
                f"{self.grafana_url}/api/datasources/proxy/{prometheus_ds_id}/api/v1/query",
                headers=headers,
                params={"query": query},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success" and data.get("data", {}).get("result"):
                    return float(data["data"]["result"][0]["value"][1])
            return None
        except Exception as e:
            self.warning(f"Ошибка запроса через Grafana: {e}")
            return None
    
    def compare_metrics_three_way(self):
        """Трехстороннее сравнение метрик: Backend ↔ Prometheus ↔ Grafana"""
        self.section("Трехстороннее сравнение метрик")
        
        # Получаем метрики из всех источников
        self.info("Получение метрик из Backend...")
        backend_metrics = self.get_backend_metrics()
        
        self.info("Получение метрик из Prometheus напрямую...")
        time.sleep(2)
        prometheus_metrics = self.get_prometheus_metrics()
        
        self.info("Получение метрик через Grafana...")
        grafana_metrics = {}
        
        if self.authenticate_grafana():
            # Active users через Grafana
            active_users = self.query_prometheus_via_grafana("active_users")
            if active_users is not None:
                grafana_metrics['active_users'] = active_users
            
            # Prediction requests через Grafana
            pred_requests = self.query_prometheus_via_grafana("sum(prediction_requests_total)")
            if pred_requests is not None:
                grafana_metrics['prediction_requests_total'] = pred_requests
        
        # Сравнение
        self.info("\nСравнение метрик:")
        
        # Active users
        if "active_users" in backend_metrics and "active_users" in prometheus_metrics:
            backend_val = backend_metrics["active_users"]
            prom_val = prometheus_metrics["active_users"]
            diff = abs(backend_val - prom_val)
            
            self.info(f"active_users:")
            self.info(f"  Backend: {backend_val}")
            self.info(f"  Prometheus: {prom_val}")
            
            if "active_users" in grafana_metrics:
                grafana_val = grafana_metrics["active_users"]
                self.info(f"  Grafana: {grafana_val}")
                
                if abs(backend_val - grafana_val) < 0.1:
                    self.success("  ✅ Backend ↔ Grafana: совпадает")
                else:
                    self.error(f"  ❌ Backend ↔ Grafana: не совпадает (разница: {abs(backend_val - grafana_val)})")
                    self.inconsistencies.append("active_users_backend_grafana")
            
            if diff < 0.1:
                self.success("  ✅ Backend ↔ Prometheus: совпадает")
            else:
                self.error(f"  ❌ Backend ↔ Prometheus: не совпадает (разница: {diff})")
                self.inconsistencies.append("active_users_backend_prometheus")
        
        # Prediction requests
        if "prediction_requests_total" in prometheus_metrics:
            prom_val = prometheus_metrics["prediction_requests_total"]
            self.info(f"\nprediction_requests_total:")
            self.info(f"  Prometheus: {prom_val}")
            
            if "prediction_requests_total" in grafana_metrics:
                grafana_val = grafana_metrics["prediction_requests_total"]
                self.info(f"  Grafana: {grafana_val}")
                
                if abs(prom_val - grafana_val) < 0.1:
                    self.success("  ✅ Prometheus ↔ Grafana: совпадает")
                else:
                    self.error(f"  ❌ Prometheus ↔ Grafana: не совпадает (разница: {abs(prom_val - grafana_val)})")
                    self.inconsistencies.append("prediction_requests_prometheus_grafana")
    
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
            
            # Prediction requests
            response = requests.get(
                f"{self.prometheus_url}/api/v1/query",
                params={"query": "sum(prediction_requests_total)"},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success" and data.get("data", {}).get("result"):
                    metrics['prediction_requests_total'] = float(data["data"]["result"][0]["value"][1])
            
            return metrics
        except Exception as e:
            self.error(f"Ошибка получения метрик Prometheus: {e}")
            return {}
    
    def check_dashboard_data(self):
        """Проверка данных на дашбордах Grafana"""
        self.section("Проверка данных на дашбордах Grafana")
        
        if not self.authenticate_grafana():
            self.warning("Не удалось аутентифицироваться - пропускаем проверку дашбордов")
            return
        
        try:
            headers = {"Cookie": self.grafana_auth}
            
            # Получаем список дашбордов
            response = requests.get(
                f"{self.grafana_url}/api/search",
                headers=headers,
                params={"type": "dash-db"},
                timeout=5
            )
            
            if response.status_code == 200:
                dashboards = response.json()
                ml_dashboards = [d for d in dashboards if "ml" in d.get("title", "").lower() or "service" in d.get("title", "").lower()]
                
                if ml_dashboards:
                    self.success(f"Найдено {len(ml_dashboards)} дашбордов ML Service")
                    for dash in ml_dashboards:
                        self.info(f"  - {dash.get('title')} (UID: {dash.get('uid')})")
                else:
                    self.warning("Дашборды ML Service не найдены")
            else:
                self.warning("Не удалось получить список дашбордов")
                
        except Exception as e:
            self.warning(f"Ошибка проверки дашбордов: {e}")
    
    def verify_data_consistency_with_grafana(self):
        """Проверка согласованности данных с Grafana"""
        self.section("Проверка согласованности данных с Grafana")
        
        # Проверяем datasource
        datasource_ok = self.check_prometheus_datasource()
        
        if datasource_ok:
            # Трехстороннее сравнение
            self.compare_metrics_three_way()
            
            # Проверка дашбордов
            self.check_dashboard_data()
        
        # Итоговый отчет
        self.section("Итоговый отчет")
        
        if self.inconsistencies:
            self.error(f"Обнаружено {len(self.inconsistencies)} несоответствий:")
            for inc in self.inconsistencies:
                self.error(f"  - {inc}")
            return False
        else:
            self.success("Все метрики согласованы между Backend, Prometheus и Grafana")
            return True


def main():
    """Главная функция"""
    checker = GrafanaConsistencyChecker()
    
    checker.section("ПРОВЕРКА СОГЛАСОВАННОСТИ С GRAFANA")
    checker.info(f"Время начала: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    checker.info(f"Backend URL: {checker.base_url}")
    checker.info(f"Prometheus URL: {checker.prometheus_url}")
    checker.info(f"Grafana URL: {checker.grafana_url}")
    
    success = checker.verify_data_consistency_with_grafana()
    
    checker.section("ПРОВЕРКА ЗАВЕРШЕНА")
    checker.info(f"Время завершения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if success:
        checker.success("✅ Все проверки пройдены успешно!")
    else:
        checker.warning("⚠️  Обнаружены несоответствия - проверьте детали выше")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
