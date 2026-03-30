import os
import time

import httpx
import streamlit as st

API = os.environ.get("API_URL", "http://localhost:8000/api")
# Совпадает с MOCK_TOPUP_SECRET у API (в Docker передаётся из compose/.env)
MOCK_TOPUP_SECRET_DEFAULT = os.environ.get("MOCK_TOPUP_SECRET", "")

st.set_page_config(page_title="ML Inference", layout="wide")
st.title("ML Inference — личный кабинет")


def api_headers() -> dict[str, str]:
    token = st.session_state.get("token")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def login_form() -> None:
    st.subheader("Вход")
    email = st.text_input("Email")
    password = st.text_input("Пароль", type="password")
    if st.button("Войти"):
        with httpx.Client(timeout=30.0) as client:
            r = client.post(
                f"{API}/auth/login",
                data={"username": email, "password": password},
            )
        if r.status_code != 200:
            st.error(r.text)
            return
        st.session_state.token = r.json()["access_token"]
        st.rerun()


def register_form() -> None:
    st.subheader("Регистрация")
    email = st.text_input("Email (регистрация)")
    password = st.text_input("Пароль (регистрация)", type="password")
    if st.button("Зарегистрироваться"):
        with httpx.Client(timeout=30.0) as client:
            r = client.post(f"{API}/auth/register", json={"email": email, "password": password})
        if r.status_code != 200:
            st.error(r.text)
            return
        st.session_state.token = r.json()["access_token"]
        st.rerun()


def dashboard() -> None:
    h = api_headers()
    with httpx.Client(timeout=120.0) as client:
        bal = client.get(f"{API}/billing/balance", headers=h)
        summ = client.get(f"{API}/analytics/summary", headers=h)
        txs = client.get(f"{API}/billing/transactions?limit=50", headers=h)
        models_r = client.get(f"{API}/models", headers=h)

    if bal.status_code != 200:
        st.error("Не удалось загрузить баланс")
        st.session_state.token = None
        st.rerun()
        return

    balance = bal.json()["balance_credits"]

    with st.sidebar:
        st.metric("Баланс (кредиты)", balance)
        if st.button("Выйти"):
            st.session_state.token = None
            st.rerun()

    if "_last_prediction_flash" in st.session_state:
        flash = st.session_state.pop("_last_prediction_flash")
        st.success("Предсказание выполнено")
        st.json(flash.get("result") or {})

    tab_stat, tab_topup, tab_models, tab_pred, tab_promo = st.tabs(
        ["Статистика", "Пополнение", "Модели", "Предсказание", "Промокод"]
    )

    with tab_stat:
        st.subheader("Сводка")
        if summ.status_code == 200:
            s = summ.json()
            total = int(s.get("prediction_jobs_total", 0))
            ok = int(s.get("prediction_jobs_success", 0))
            fail = int(s.get("prediction_jobs_failed", 0))
            spent = int(s.get("credits_spent", 0))
            success_pct = round(100.0 * ok / total, 1) if total > 0 else 0.0

            m1, m2, m3 = st.columns(3)
            m1.metric("Всего задач предсказания", total)
            m2.metric("Потрачено кредитов", spent)
            m3.metric("Доля успешных", f"{success_pct} %")

            m4, m5 = st.columns(2)
            m4.metric("Успешных", ok)
            m5.metric("С ошибкой", fail)
        else:
            st.warning("Статистика по задачам временно недоступна.")

        st.subheader("Последние транзакции")
        if txs.status_code == 200:
            st.dataframe(txs.json(), use_container_width=True)
        else:
            st.warning("Не удалось загрузить транзакции")

    with tab_topup:
        st.subheader("Пополнение баланса (mock)")
        with st.form("mock_topup"):
            credits = st.number_input("Кредиты для зачисления", min_value=1, value=100, step=10)
            secret = st.text_input(
                "Секрет mock-topup",
                value=MOCK_TOPUP_SECRET_DEFAULT,
                type="password",
                help="По умолчанию подставляется из переменной окружения Streamlit (MOCK_TOPUP_SECRET).",
            )
            submitted = st.form_submit_button("Зачислить кредиты")
            if submitted:
                if not secret.strip():
                    st.error("Укажите секрет.")
                else:
                    payload = {
                        "amount_money": str(int(credits)),
                        "credits_to_grant": int(credits),
                        "secret": secret.strip(),
                    }
                    with httpx.Client(timeout=30.0) as client:
                        r = client.post(
                            f"{API}/billing/mock-topup",
                            headers=h,
                            json=payload,
                        )
                    if r.status_code == 200:
                        st.success(r.json())
                        st.rerun()
                    else:
                        st.error(r.text)

    with tab_models:
        st.subheader("Ваши модели")
        if models_r.status_code == 200:
            rows = models_r.json()
            if rows:
                st.dataframe(rows, use_container_width=True)
            else:
                st.info("Пока нет загруженных моделей.")
        else:
            st.warning(f"Не удалось получить список моделей: {models_r.status_code}")

        st.subheader("Загрузить модель")
        with st.form("upload_model", clear_on_submit=True):
            mname = st.text_input("Название модели", placeholder="my_classifier")
            upfile = st.file_uploader(
                "Файл модели (.joblib / .pkl)",
                type=["joblib", "pkl", "pickle"],
            )
            submitted = st.form_submit_button("Загрузить на сервер")
            if submitted:
                if not mname.strip():
                    st.error("Укажите название модели.")
                elif upfile is None:
                    st.error("Выберите файл.")
                else:
                    files = {
                        "file": (
                            upfile.name,
                            upfile.getvalue(),
                            "application/octet-stream",
                        )
                    }
                    data = {"name": mname.strip()}
                    with httpx.Client(timeout=120.0) as client:
                        ur = client.post(
                            f"{API}/models",
                            headers=h,
                            files=files,
                            data=data,
                        )
                    if ur.status_code == 200:
                        st.success(f"Модель загружена: id={ur.json().get('id')}")
                        st.rerun()
                    else:
                        st.error(ur.text)

    with tab_pred:
        st.subheader("Предсказание")
        if models_r.status_code != 200:
            st.warning("Не удалось загрузить список моделей.")
        else:
            rows = models_r.json()
            active = [m for m in rows if m.get("is_active", True)]
            if not active:
                st.warning("Нет активных моделей. Загрузите модель на вкладке «Модели».")
            else:
                labels = [f"{m['name']} (id={m['id']})" for m in active]
                picked = st.selectbox("Модель", labels, key="predict_model_select")
                model_id = active[labels.index(picked)]["id"]
                features_raw = st.text_input(
                    "Признаки (числа через запятую)",
                    value="5.1, 3.5, 1.4, 0.2",
                    help="Для Iris — 4 числа; для другой модели — столько признаков, сколько ожидает модель.",
                    key="predict_features",
                )
                if st.button("Запустить предсказание"):
                    try:
                        parts = [p.strip() for p in features_raw.replace(";", ",").split(",") if p.strip()]
                        features = [float(x) for x in parts]
                    except ValueError as e:
                        st.error(f"Некорректные числа: {e}")
                    else:
                        if not features:
                            st.error("Укажите хотя бы одно число.")
                        else:
                            with httpx.Client(timeout=60.0) as client:
                                pr = client.post(
                                    f"{API}/predict",
                                    headers=h,
                                    json={"model_id": model_id, "features": features},
                                )
                            if pr.status_code == 402:
                                st.error("Недостаточно кредитов. Пополните баланс.")
                            elif pr.status_code != 200:
                                st.error(pr.text)
                            else:
                                job_id = pr.json()["job_id"]
                                with st.spinner(f"Задача #{job_id}: ожидание воркера…"):
                                    deadline = time.monotonic() + 120.0
                                    status_body: dict | None = None
                                    while time.monotonic() < deadline:
                                        with httpx.Client(timeout=30.0) as client:
                                            jr = client.get(
                                                f"{API}/jobs/{job_id}",
                                                headers=h,
                                            )
                                        if jr.status_code != 200:
                                            st.error(jr.text)
                                            status_body = None
                                            break
                                        status_body = jr.json()
                                        job_status = status_body.get("status")
                                        if job_status in ("success", "failed"):
                                            break
                                        time.sleep(0.4)
                                    else:
                                        st.error(
                                            "Таймаут ожидания результата. Проверьте воркер Celery и GET /api/jobs/"
                                            + str(job_id)
                                        )
                                        status_body = None
                                if status_body and status_body.get("status") == "success":
                                    # Баланс в начале run запрошен до списания; rerun подтягивает актуальный баланс в сайдбаре.
                                    st.session_state["_last_prediction_flash"] = {
                                        "result": status_body.get("result"),
                                    }
                                    st.rerun()
                                elif status_body and status_body.get("status") == "failed":
                                    st.error(
                                        status_body.get("error_message")
                                        or status_body.get("status")
                                    )

    with tab_promo:
        st.subheader("Промокод")
        code = st.text_input("Код", key="promo_code")
        if st.button("Активировать"):
            with httpx.Client(timeout=30.0) as client:
                r = client.post(f"{API}/promocodes/activate", headers=h, json={"code": code})
            if r.status_code == 200:
                st.success(r.json())
                st.rerun()
            else:
                st.error(r.text)


if not st.session_state.get("token"):
    tab1, tab2 = st.tabs(["Вход", "Регистрация"])
    with tab1:
        login_form()
    with tab2:
        register_form()
else:
    dashboard()
