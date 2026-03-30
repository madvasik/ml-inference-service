#!/usr/bin/env python3
"""
E2E-сценарий через публичные ручки API:

  1) Регистрация → mock-пополнение → модель → первое предсказание (успех)
  2) Повторный вход → промокод WELCOME (первая активация — успех, вторая — 409)
  3) Второе предсказание (успех) → третье с неверными признаками (failed воркера)

Промокод WELCOME добавляется миграцией alembic (20250331_0002).

  export MOCK_TOPUP_SECRET=dev-mock-topup-secret
  python scripts/demo_user_flow.py --base-url http://localhost:8001/api

Опционально: --promocode OTHER, --model-path scripts/sample_models/example_model.joblib (от корня репо)
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx
import joblib
from sklearn.linear_model import LinearRegression

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Демо-сценарий ML Inference API (расширенный)")
    p.add_argument(
        "--base-url",
        default=os.environ.get("API_URL", "http://localhost:8001/api"),
        help="Базовый URL API",
    )
    p.add_argument(
        "--email",
        default="",
        help="Email (по умолчанию demo-<unixtime>@example.com)",
    )
    p.add_argument("--password", default="password12", help="Пароль")
    p.add_argument(
        "--mock-secret",
        default=os.environ.get("MOCK_TOPUP_SECRET", "dev-mock-topup-secret"),
        help="Секрет POST /billing/mock-topup",
    )
    p.add_argument("--topup-credits", type=int, default=100, help="Кредитов при первом mock-пополнении")
    p.add_argument(
        "--promocode",
        default=os.environ.get("DEMO_PROMOCODE", "WELCOME"),
        help="Код для активации (по умолчанию WELCOME из миграции)",
    )
    p.add_argument(
        "--skip-funding",
        action="store_true",
        help="Не вызывать mock-topup (уже есть кредиты на новом аккаунте)",
    )
    p.add_argument(
        "--model-path",
        type=Path,
        default=None,
        help="Путь к .joblib; иначе временная LinearRegression с 1 признаком",
    )
    p.add_argument(
        "--features-ok",
        default="3.0",
        help="Корректные признаки под модель (для Iris из scripts/sample_models — четыре числа через запятую)",
    )
    p.add_argument(
        "--features-bad",
        default="1.0,2.0,3.0",
        help="Неверная размерность для временной LR(1 признак); для своей модели подберите сами",
    )
    p.add_argument("--job-timeout", type=float, default=120.0, help="Таймаут ожидания задачи Celery")
    return p.parse_args()


def register_only(client: httpx.Client, base: str, email: str, password: str) -> str:
    r = client.post(f"{base}/auth/register", json={"email": email, "password": password})
    if r.status_code != 200:
        r.raise_for_status()
    print("1) Регистрация: ok")
    return r.json()["access_token"]


def login_only(client: httpx.Client, base: str, email: str, password: str) -> str:
    r = client.post(
        f"{base}/auth/login",
        data={"username": email, "password": password},
    )
    r.raise_for_status()
    print("   Вход: ok")
    return r.json()["access_token"]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def ensure_model_file(path: Path | None) -> tuple[Path, bool]:
    if path is not None and path.is_file():
        print(f"   Файл модели: {path}")
        return path.resolve(), False
    tmp = tempfile.NamedTemporaryFile(suffix=".joblib", delete=False)
    p = Path(tmp.name)
    tmp.close()
    model = LinearRegression()
    model.fit([[1.0], [2.0]], [1.0, 2.0])
    joblib.dump(model, p)
    print(f"   Временная LinearRegression (1 признак): {p}")
    return p, True


def parse_features(s: str) -> list[float]:
    parts = [x.strip() for x in s.replace(";", ",").split(",") if x.strip()]
    return [float(x) for x in parts]


def wait_for_job(
    client: httpx.Client,
    base: str,
    h: dict[str, str],
    job_id: int,
    timeout: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        jr = client.get(f"{base}/jobs/{job_id}", headers=h)
        jr.raise_for_status()
        body = jr.json()
        if body.get("status") in ("success", "failed"):
            return body
        time.sleep(0.5)
    raise TimeoutError(f"job {job_id}: таймаут ожидания воркера")


def run_predict(
    client: httpx.Client,
    base: str,
    h: dict[str, str],
    model_id: int,
    features: list[float],
    step_label: str,
    timeout: float,
    *,
    expect_success: bool,
) -> dict[str, Any] | None:
    pr = client.post(
        f"{base}/predict",
        headers=h,
        json={"model_id": model_id, "features": features},
    )
    if pr.status_code == 402:
        print(f"{step_label} Недостаточно кредитов.", file=sys.stderr)
        return None
    pr.raise_for_status()
    job_id = pr.json()["job_id"]
    print(f"{step_label} Задача #{job_id}, признаки {features}")
    body = wait_for_job(client, base, h, job_id, timeout)
    status = body.get("status")
    if expect_success:
        if status != "success":
            print(f"{step_label} Ожидался success, получено: {body}", file=sys.stderr)
            return None
        print(f"{step_label} → success: {body.get('result')}")
    else:
        if status != "failed":
            print(f"{step_label} Ожидался failed, получено: {body}", file=sys.stderr)
            return None
        print(f"{step_label} → failed (ожидаемо): {body.get('error_message')}")
    return body


def main() -> int:
    args = parse_args()
    email = args.email or f"demo-{int(time.time())}@example.com"
    base = args.base_url.rstrip("/")

    promo = (args.promocode or "").strip()

    try:
        features_ok = parse_features(args.features_ok)
        features_bad = parse_features(args.features_bad)
    except ValueError as e:
        print(f"Некорректные признаки: {e}", file=sys.stderr)
        return 1
    if not features_ok:
        print("Нужен хотя бы один признак в --features-ok", file=sys.stderr)
        return 1
    if not features_bad:
        print("Нужен хотя бы один признак в --features-bad", file=sys.stderr)
        return 1

    model_path = args.model_path
    if model_path is not None and not model_path.is_absolute():
        # Путь от корня репозитория (например scripts/sample_models/...)
        model_path = REPO_ROOT / model_path

    with httpx.Client(timeout=120.0) as client:
        token = register_only(client, base, email, args.password)
        h = headers(token)

        r = client.get(f"{base}/billing/balance", headers=h)
        r.raise_for_status()
        print(f"2) Баланс: {r.json()['balance_credits']}")

        if not args.skip_funding:
            r = client.post(
                f"{base}/billing/mock-topup",
                headers=h,
                json={
                    "amount_money": str(int(args.topup_credits)),
                    "credits_to_grant": int(args.topup_credits),
                    "secret": args.mock_secret,
                },
            )
            if r.status_code != 200:
                print(f"3) Mock-topup: {r.status_code} {r.text}", file=sys.stderr)
                return 1
            print(f"3) Mock-пополнение (+{args.topup_credits}): {r.json()}")
        else:
            print("3) Mock-пополнение пропущено (--skip-funding)")

        r = client.get(f"{base}/billing/balance", headers=h)
        r.raise_for_status()
        bal = r.json()["balance_credits"]
        print(f"4) Баланс: {bal}")
        if bal < 1:
            print("Нужен хотя бы 1 кредит для первого предсказания.", file=sys.stderr)
            return 1

        mf, mf_is_temp = ensure_model_file(model_path)
        try:
            r = client.post(
                f"{base}/models",
                headers=h,
                data={"name": "demo_flow_model"},
                files={"file": (mf.name, mf.read_bytes(), "application/octet-stream")},
            )
        finally:
            if mf_is_temp:
                mf.unlink(missing_ok=True)
        r.raise_for_status()
        mid = r.json()["id"]
        print(f"5) Модель загружена: id={mid}")

        r = client.get(f"{base}/models", headers=h)
        r.raise_for_status()
        print(f"6) Моделей в списке: {len(r.json())}")

        if (
            run_predict(
                client,
                base,
                h,
                mid,
                features_ok,
                "7) Первое предсказание:",
                args.job_timeout,
                expect_success=True,
            )
            is None
        ):
            return 1

        r = client.get(f"{base}/billing/balance", headers=h)
        r.raise_for_status()
        print(f"8) Баланс после 1-го predict: {r.json()['balance_credits']}")

        print("9) Повторный вход тем же email/паролем…")
        token2 = login_only(client, base, email, args.password)
        h2 = headers(token2)

        r = client.post(f"{base}/promocodes/activate", headers=h2, json={"code": promo})
        if r.status_code != 200:
            print(
                f"10) Промокод «{promo}» (первая активация): ошибка {r.status_code} — {r.text}",
                file=sys.stderr,
            )
            return 1
        print(f"10) Промокод «{promo}» (первая активация): {r.json()}")

        r2 = client.post(f"{base}/promocodes/activate", headers=h2, json={"code": promo})
        if r2.status_code != 409:
            print(
                f"11) Повторная активация «{promo}»: ожидался HTTP 409, "
                f"получено {r2.status_code} — {r2.text}",
                file=sys.stderr,
            )
            return 1
        detail = r2.json().get("detail", r2.text)
        print(f"11) Повторная активация «{promo}»: ожидаемая ошибка 409 — {detail}")

        r = client.get(f"{base}/billing/balance", headers=h2)
        r.raise_for_status()
        print(f"12) Баланс: {r.json()['balance_credits']}")

        if (
            run_predict(
                client,
                base,
                h2,
                mid,
                features_ok,
                "13) Второе предсказание (после промокода):",
                args.job_timeout,
                expect_success=True,
            )
            is None
        ):
            return 1

        if (
            run_predict(
                client,
                base,
                h2,
                mid,
                features_bad,
                "14) Третье предсказание (некорректные признаки):",
                args.job_timeout,
                expect_success=False,
            )
            is None
        ):
            return 1

        r = client.get(f"{base}/billing/balance", headers=h2)
        r.raise_for_status()
        print(f"15) Баланс итог: {r.json()['balance_credits']}")

        r = client.get(f"{base}/analytics/summary", headers=h2)
        if r.status_code == 200:
            s = r.json()
            print(
                "16) Аналитика: "
                f"задач={s.get('prediction_jobs_total')}, "
                f"успех={s.get('prediction_jobs_success')}, "
                f"ошибок={s.get('prediction_jobs_failed')}, "
                f"кредитов потрачено={s.get('credits_spent')}"
            )
        else:
            print(f"16) Аналитика: HTTP {r.status_code}")

    print("Готово.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except TimeoutError as e:
        print(e, file=sys.stderr)
        print("Проверьте, что Celery worker запущен.", file=sys.stderr)
        raise SystemExit(1)
