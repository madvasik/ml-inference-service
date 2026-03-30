from __future__ import annotations

from typing import Any

import requests
import streamlit as st

try:
    from dashboard.config import API_TIMEOUT_SECONDS, BASE_URL
except ModuleNotFoundError:
    from config import API_TIMEOUT_SECONDS, BASE_URL


class APIClient:
    """Second value in fetch_* tuples is AUTH_ERROR when token is rejected (401/403)."""

    AUTH_ERROR = "auth"

    def __init__(self, base_url: str = BASE_URL, timeout: int = API_TIMEOUT_SECONDS):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _headers(self, token: str | None = None) -> dict[str, str]:
        if token is None:
            return {}
        return {"Authorization": f"Bearer {token}"}

    def login(self, email: str, password: str) -> tuple[bool, str | None, dict[str, Any] | None, str | None]:
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/auth/login",
                json={"email": email, "password": password},
                timeout=self.timeout,
            )
            if response.status_code != 200:
                return False, None, None, "Неверный email или пароль"

            token = response.json()["access_token"]
            user_response = requests.get(
                f"{self.base_url}/api/v1/users/me",
                headers=self._headers(token),
                timeout=self.timeout,
            )
            if user_response.status_code != 200:
                return False, None, None, "Не удалось получить профиль пользователя"
            return True, token, user_response.json(), None
        except requests.RequestException as exc:
            return False, None, None, f"Ошибка подключения к API: {exc}"

    def fetch_users(self, token: str) -> tuple[list[dict[str, Any]], str | None]:
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/admin/users",
                headers=self._headers(token),
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.json(), None
            if response.status_code in (401, 403):
                return [], self.AUTH_ERROR
            return [], None
        except requests.RequestException as exc:
            st.error(f"Ошибка получения пользователей: {exc}")
            return [], None

    def fetch_predictions(
        self,
        token: str,
        user_id: int | None = None,
        model_id: int | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        params: dict[str, Any] = {}
        if user_id is not None:
            params["user_id"] = user_id
        if model_id is not None:
            params["model_id"] = model_id

        empty: dict[str, Any] = {"predictions": [], "total": 0}
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/admin/predictions",
                headers=self._headers(token),
                params=params,
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.json(), None
            if response.status_code in (401, 403):
                return empty, self.AUTH_ERROR
            return empty, None
        except requests.RequestException as exc:
            st.error(f"Ошибка получения предсказаний: {exc}")
            return empty, None

    def fetch_transactions(self, token: str, user_id: int | None = None) -> tuple[dict[str, Any], str | None]:
        params: dict[str, Any] = {}
        if user_id is not None:
            params["user_id"] = user_id

        empty: dict[str, Any] = {"transactions": [], "total": 0}
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/admin/transactions",
                headers=self._headers(token),
                params=params,
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.json(), None
            if response.status_code in (401, 403):
                return empty, self.AUTH_ERROR
            return empty, None
        except requests.RequestException as exc:
            st.error(f"Ошибка получения транзакций: {exc}")
            return empty, None

    def fetch_payments(self, token: str, user_id: int | None = None) -> tuple[dict[str, Any], str | None]:
        params: dict[str, Any] = {}
        if user_id is not None:
            params["user_id"] = user_id

        empty: dict[str, Any] = {"payments": [], "total": 0}
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/admin/payments",
                headers=self._headers(token),
                params=params,
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.json(), None
            if response.status_code in (401, 403):
                return empty, self.AUTH_ERROR
            return empty, None
        except requests.RequestException as exc:
            st.error(f"Ошибка получения платежей: {exc}")
            return empty, None
