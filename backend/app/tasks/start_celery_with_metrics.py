#!/usr/bin/env python3
"""
Скрипт для запуска Celery worker с метриками Prometheus
"""
import os
import sys
import subprocess
import threading
from pathlib import Path
from prometheus_client import start_http_server, multiprocess, CollectorRegistry, generate_latest
from prometheus_client import CONTENT_TYPE_LATEST
from http.server import HTTPServer, BaseHTTPRequestHandler

# Включаем multiprocess mode для prometheus_client
# Это позволяет метрикам из разных процессов попадать в один endpoint
os.environ['PROMETHEUS_MULTIPROC_DIR'] = os.getenv('PROMETHEUS_MULTIPROC_DIR', '/tmp/prometheus_multiproc_dir')

# Создаем директорию для multiprocess метрик если её нет
if not os.path.exists(os.environ['PROMETHEUS_MULTIPROC_DIR']):
    os.makedirs(os.environ['PROMETHEUS_MULTIPROC_DIR'])


def prepare_multiprocess_dir() -> None:
    """Очищает stale Prometheus файлы перед запуском нового worker."""
    metrics_dir = Path(os.environ["PROMETHEUS_MULTIPROC_DIR"])
    metrics_dir.mkdir(parents=True, exist_ok=True)
    for entry in metrics_dir.iterdir():
        if entry.is_file():
            entry.unlink()

class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler для метрик с поддержкой multiprocess"""
    def do_GET(self):
        if self.path == '/metrics':
            try:
                registry = CollectorRegistry()
                multiprocess.MultiProcessCollector(registry)
                output = generate_latest(registry)
                self.send_response(200)
                self.send_header('Content-Type', CONTENT_TYPE_LATEST)
                self.end_headers()
                self.wfile.write(output)
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f"Error: {e}".encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Отключаем логирование запросов

def start_metrics_server():
    """Запуск HTTP сервера для метрик Prometheus"""
    metrics_port = int(os.getenv("METRICS_PORT", "9091"))
    try:
        server = HTTPServer(('0.0.0.0', metrics_port), MetricsHandler)
        print(f"✓ Prometheus metrics server started on port {metrics_port} (multiprocess mode)")
        server.serve_forever()
    except Exception as e:
        print(f"✗ Failed to start metrics server: {e}")

if __name__ == "__main__":
    prepare_multiprocess_dir()

    # Запускаем метрики сервер если включено
    if os.getenv("ENABLE_METRICS_SERVER", "false").lower() == "true":
        metrics_thread = threading.Thread(target=start_metrics_server, daemon=True)
        metrics_thread.start()
        print("Metrics server thread started")
    
    # Запускаем Celery worker
    cmd = ["celery", "-A", "backend.app.tasks.celery_app", "worker", "--loglevel=info"]
    sys.exit(subprocess.call(cmd))
