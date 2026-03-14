"""
Общие утилиты для логирования в тестах
"""
import os
import json
import time
import requests
from typing import Optional


class DetailedLogger:
    """Класс для подробного логирования в тестах"""
    
    def __init__(self, verbose: bool = True, debug: bool = False):
        self.verbose = verbose or os.getenv("VERBOSE_TESTS", "true").lower() == "true"
        self.debug_mode = debug or os.getenv("DEBUG_TESTS", "false").lower() == "true"
        self.request_count = 0
        
    def log_request(self, method: str, url: str, headers: dict = None, data: dict = None, files: dict = None):
        """Логирование HTTP запроса"""
        if self.verbose:
            self.request_count += 1
            print(f"🔍 [REQ #{self.request_count}] → {method} {url}")
            if headers:
                safe_headers = {k: (v[:50] + '...' if isinstance(v, str) and len(v) > 50 else v) 
                               for k, v in headers.items() if k != 'Authorization'}
                if safe_headers:
                    print(f"   Headers: {json.dumps(safe_headers, indent=2, ensure_ascii=False)}")
            if data:
                data_str = json.dumps(data, indent=2, ensure_ascii=False)
                print(f"   Body: {data_str[:500]}{'...' if len(data_str) > 500 else ''}")
            if files:
                print(f"   Files: {list(files.keys())}")
    
    def log_response(self, response: requests.Response, show_body: bool = False, max_body_length: int = 500):
        """Логирование HTTP ответа"""
        if self.verbose:
            status_emoji = "✅" if 200 <= response.status_code < 300 else "❌"
            print(f"🔍 [RESP] {status_emoji} ← {response.status_code} {response.reason}")
            if show_body and response.text:
                try:
                    body = json.loads(response.text)
                    body_str = json.dumps(body, indent=2, ensure_ascii=False)
                    print(f"   Response: {body_str[:max_body_length]}{'...' if len(body_str) > max_body_length else ''}")
                except:
                    print(f"   Response: {response.text[:max_body_length]}{'...' if len(response.text) > max_body_length else ''}")
    
    def log_timing(self, operation: str, duration: float):
        """Логирование времени выполнения"""
        if self.verbose:
            print(f"⏱️  [{operation}] {duration:.3f}s")
    
    def log_debug(self, message: str):
        """Отладочное сообщение"""
        if self.debug_mode or self.verbose:
            print(f"🔍 [DEBUG] {message}")
    
    def log_error_details(self, error: Exception, context: str = ""):
        """Детальное логирование ошибки"""
        print(f"❌ [ERROR] {context}: {error}")
        if self.debug_mode:
            import traceback
            print(f"   Traceback:\n{traceback.format_exc()}")
    
    def log_step(self, step_name: str, step_number: int = None, total_steps: int = None):
        """Логирование шага выполнения"""
        if self.verbose:
            step_info = f"Шаг {step_number}/{total_steps}: " if step_number else ""
            print(f"📍 {step_info}{step_name}")
