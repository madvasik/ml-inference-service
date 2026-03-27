"""
HTTP сервер для экспорта метрик Prometheus из Celery worker
"""
from prometheus_client import start_http_server
import os
import threading
import logging

logger = logging.getLogger(__name__)


def start_metrics_server():
    """Запуск HTTP сервера для метрик Prometheus"""
    metrics_port = int(os.getenv("METRICS_PORT", "9091"))
    try:
        # Запускаем в отдельном потоке, чтобы не блокировать Celery worker
        def run_server():
            try:
                start_http_server(metrics_port)
                logger.info(f"✓ Prometheus metrics server started on port {metrics_port}")
                print(f"✓ Prometheus metrics server started on port {metrics_port}")
            except Exception as e:
                logger.error(f"Failed to start metrics server: {e}")
                print(f"✗ Failed to start metrics server: {e}")
        
        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        logger.info(f"Metrics server thread started for port {metrics_port}")
        print(f"Metrics server thread started for port {metrics_port}")
        return thread
    except Exception as e:
        logger.error(f"Error starting metrics server: {e}")
        print(f"Error starting metrics server: {e}")
        return None
