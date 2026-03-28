from __future__ import annotations

from typing import Any

import requests
import streamlit as st

try:
    from dashboard.config import API_TIMEOUT_SECONDS, BASE_URL
except ModuleNotFoundError:
    from config import API_TIMEOUT_SECONDS, BASE_URL


class APIClient:
    def __init__(self, base_url: str = BASE_URL, timeout: int = API_TIMEOUT_SECONDS):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _headers(self, token: str | None = None) -> dict[str, str]:
        if token is None:
            return {}
        return {"Authorization": f"Bearer {token}"}

    def login(self, email: str, password: str) -> tuple[bool, str | None, dict[str, Any] | None]:
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/auth/login",
                json={"email": email, "password": password},
                timeout=self.timeout,
            )
            if response.status_code != 200:
                return False, None, None

            token = response.json()["access_token"]
            user_response = requests.get(
                f"{self.base_url}/api/v1/users/me",
                headers=self._headers(token),
                timeout=self.timeout,
            )
            if user_response.status_code != 200:
                return False, None, None
            return True, token, user_response.json()
        except requests.RequestException as exc:
            st.error(f"Ошибка подключения к API: {exc}")
            return False, None, None

    def fetch_users(self, token: str) -> list[dict[str, Any]]:
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/admin/users",
                headers=self._headers(token),
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.json()
            return []
        except requests.RequestException as exc:
            st.error(f"Ошибка получения пользователей: {exc}")
            return []

    def fetch_predictions(
        self,
        token: str,
        user_id: int | None = None,
        model_id: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if user_id is not None:
            params["user_id"] = user_id
        if model_id is not None:
            params["model_id"] = model_id

        try:
            response = requests.get(
                f"{self.base_url}/api/v1/admin/predictions",
                headers=self._headers(token),
                params=params,
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.json()
            return {"predictions": [], "total": 0}
        except requests.RequestException as exc:
            st.error(f"Ошибка получения предсказаний: {exc}")
            return {"predictions": [], "total": 0}

    def fetch_transactions(self, token: str, user_id: int | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if user_id is not None:
            params["user_id"] = user_id

        try:
            response = requests.get(
                f"{self.base_url}/api/v1/admin/transactions",
                headers=self._headers(token),
                params=params,
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.json()
            return {"transactions": [], "total": 0}
        except requests.RequestException as exc:
            st.error(f"Ошибка получения транзакций: {exc}")
            return {"transactions": [], "total": 0}

    def fetch_payments(self, token: str, user_id: int | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if user_id is not None:
            params["user_id"] = user_id

        try:
            response = requests.get(
                f"{self.base_url}/api/v1/admin/payments",
                headers=self._headers(token),
                params=params,
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.json()
            return {"payments": [], "total": 0}
        except requests.RequestException as exc:
            st.error(f"Ошибка получения платежей: {exc}")
            return {"payments": [], "total": 0}
