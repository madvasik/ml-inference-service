import json

import pandas as pd
import plotly.express as px
import streamlit as st

try:
    from dashboard.api_client import APIClient
except ModuleNotFoundError:
    from api_client import APIClient


def render_users_tab(api_client: APIClient, token: str) -> None:
    st.header("Список всех пользователей")

    users, auth_err = api_client.fetch_users(token)
    if auth_err == APIClient.AUTH_ERROR:
        st.error("Сессия истекла или недостаточно прав. Выйдите и войдите снова.")
        return
    if not users:
        st.warning("Пользователи не найдены")
        return

    df_users = pd.DataFrame(users)
    df_users["created_at"] = pd.to_datetime(df_users["created_at"])

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Всего пользователей", len(df_users))
    with col2:
        st.metric("Администраторов", len(df_users[df_users["role"] == "admin"]))
    with col3:
        gold_users = len(df_users[df_users["loyalty_tier"] == "gold"]) if "loyalty_tier" in df_users else 0
        st.metric("Gold пользователей", gold_users)

    df_users["date"] = df_users["created_at"].dt.date
    registrations = df_users.groupby("date").size().reset_index(name="count")
    fig = px.line(
        registrations,
        x="date",
        y="count",
        title="Регистрации пользователей по датам",
        labels={"date": "Дата", "count": "Количество"},
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Детальная информация")
    st.dataframe(
        df_users[["id", "email", "role", "loyalty_tier", "loyalty_discount_percent", "created_at"]],
        use_container_width=True,
        hide_index=True,
    )


def _parse_jsonish(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def render_predictions_tab(api_client: APIClient, token: str) -> None:
    st.header("Все предсказания")

    col1, col2 = st.columns(2)
    with col1:
        filter_user_id = st.number_input(
            "Фильтр по User ID",
            min_value=0,
            value=0,
            step=1,
            help="Введите User ID для фильтрации (0 = без фильтра)",
        )
    with col2:
        filter_model_id = st.number_input(
            "Фильтр по Model ID",
            min_value=0,
            value=0,
            step=1,
            help="Введите Model ID для фильтрации (0 = без фильтра)",
        )

    predictions_data, auth_err = api_client.fetch_predictions(
        token,
        user_id=int(filter_user_id) if filter_user_id > 0 else None,
        model_id=int(filter_model_id) if filter_model_id > 0 else None,
    )
    if auth_err == APIClient.AUTH_ERROR:
        st.error("Сессия истекла или недостаточно прав. Выйдите и войдите снова.")
        return
    predictions = predictions_data.get("predictions", [])
    total = predictions_data.get("total", 0)

    if not predictions:
        st.warning("Предсказания не найдены")
        return

    df_pred = pd.DataFrame(predictions)
    df_pred["created_at"] = pd.to_datetime(df_pred["created_at"])

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Всего предсказаний", total)
    with col2:
        st.metric("Успешных", len(df_pred[df_pred["status"] == "completed"]))
    with col3:
        st.metric("Неудачных", len(df_pred[df_pred["status"] == "failed"]))
    with col4:
        st.metric("Всего кредитов потрачено", int(df_pred["credits_spent"].sum()))
    with col5:
        discount = int(df_pred["discount_amount"].sum()) if "discount_amount" in df_pred else 0
        st.metric("Суммарная скидка", discount)

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        status_counts = df_pred["status"].value_counts()
        fig_status = px.pie(values=status_counts.values, names=status_counts.index, title="Распределение по статусам")
        st.plotly_chart(fig_status, use_container_width=True)
    with chart_col2:
        df_pred["date"] = df_pred["created_at"].dt.date
        pred_by_date = df_pred.groupby("date").size().reset_index(name="count")
        fig_time = px.bar(
            pred_by_date,
            x="date",
            y="count",
            title="Предсказания по датам",
            labels={"date": "Дата", "count": "Количество"},
        )
        st.plotly_chart(fig_time, use_container_width=True)

    st.subheader("Детальная информация")
    st.dataframe(
        df_pred[["id", "user_id", "model_id", "status", "credits_spent", "created_at"]],
        use_container_width=True,
        hide_index=True,
    )

    selected_id = st.selectbox("Выберите предсказание для детального просмотра", df_pred["id"].tolist())
    selected_pred = df_pred[df_pred["id"] == selected_id].iloc[0]
    with st.expander(f"Детали предсказания #{selected_id}"):
        st.json(
            {
                "input_data": _parse_jsonish(selected_pred["input_data"]),
                "result": _parse_jsonish(selected_pred["result"]),
                "status": selected_pred["status"],
                "base_cost": int(selected_pred["base_cost"]),
                "discount_percent": int(selected_pred["discount_percent"]),
                "discount_amount": int(selected_pred["discount_amount"]),
                "credits_spent": int(selected_pred["credits_spent"]),
                "failure_reason": selected_pred.get("failure_reason"),
            }
        )


def render_payments_tab(api_client: APIClient, token: str) -> None:
    st.header("Платежи")

    payments_data, auth_err = api_client.fetch_payments(token)
    if auth_err == APIClient.AUTH_ERROR:
        st.error("Сессия истекла или недостаточно прав. Выйдите и войдите снова.")
        return
    payments = payments_data.get("payments", [])
    total = payments_data.get("total", 0)

    if not payments:
        st.warning("Платежи не найдены")
        return

    df_payments = pd.DataFrame(payments)
    df_payments["created_at"] = pd.to_datetime(df_payments["created_at"])
    if "confirmed_at" in df_payments:
        df_payments["confirmed_at"] = pd.to_datetime(df_payments["confirmed_at"])

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Всего платежей", total)
    with col2:
        st.metric("Подтвержденных", len(df_payments[df_payments["status"] == "confirmed"]))
    with col3:
        confirmed_amount = df_payments[df_payments["status"] == "confirmed"]["amount"].sum()
        st.metric("Начислено кредитов", int(confirmed_amount))

    status_counts = df_payments["status"].value_counts()
    fig_status = px.pie(values=status_counts.values, names=status_counts.index, title="Статусы платежей")
    st.plotly_chart(fig_status, use_container_width=True)

    st.dataframe(
        df_payments[["id", "user_id", "provider", "status", "amount", "external_id", "created_at", "confirmed_at"]],
        use_container_width=True,
        hide_index=True,
    )


def render_transactions_tab(api_client: APIClient, token: str) -> None:
    st.header("Транзакции")

    filter_user_id = st.number_input(
        "Фильтр по User ID",
        min_value=0,
        value=0,
        step=1,
        key="filter_user_id_transactions",
        help="Введите User ID для фильтрации транзакций (0 = без фильтра)",
    )
    transactions_data, auth_err = api_client.fetch_transactions(
        token,
        user_id=int(filter_user_id) if filter_user_id > 0 else None,
    )
    if auth_err == APIClient.AUTH_ERROR:
        st.error("Сессия истекла или недостаточно прав. Выйдите и войдите снова.")
        return
    transactions = transactions_data.get("transactions", [])
    total = transactions_data.get("total", 0)

    if not transactions:
        st.warning("Транзакции не найдены")
        return

    df_trans = pd.DataFrame(transactions)
    df_trans["created_at"] = pd.to_datetime(df_trans["created_at"])

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Всего транзакций", total)
    with col2:
        credits = int(df_trans[df_trans["type"] == "credit"]["amount"].sum())
        st.metric("Всего пополнено", f"{credits} кредитов")
    with col3:
        debits = int(df_trans[df_trans["type"] == "debit"]["amount"].sum())
        st.metric("Всего потрачено", f"{debits} кредитов")

    df_trans["date"] = df_trans["created_at"].dt.date
    trans_by_date = df_trans.groupby(["date", "type"])["amount"].sum().reset_index()
    fig_trans = px.bar(
        trans_by_date,
        x="date",
        y="amount",
        color="type",
        title="Транзакции по датам",
        labels={"date": "Дата", "amount": "Сумма (кредиты)", "type": "Тип"},
    )
    st.plotly_chart(fig_trans, use_container_width=True)

    st.subheader("Детальная информация")
    st.dataframe(
        df_trans[["id", "user_id", "type", "amount", "description", "created_at"]],
        use_container_width=True,
        hide_index=True,
    )


def render_stats_tab(api_client: APIClient, token: str) -> None:
    st.header("Общая статистика")

    users, auth_err = api_client.fetch_users(token)
    if auth_err == APIClient.AUTH_ERROR:
        st.error("Сессия истекла или недостаточно прав. Выйдите и войдите снова.")
        return
    predictions_data, auth_err = api_client.fetch_predictions(token)
    if auth_err == APIClient.AUTH_ERROR:
        st.error("Сессия истекла или недостаточно прав. Выйдите и войдите снова.")
        return
    predictions = predictions_data.get("predictions", [])
    payments_data, auth_err = api_client.fetch_payments(token)
    if auth_err == APIClient.AUTH_ERROR:
        st.error("Сессия истекла или недостаточно прав. Выйдите и войдите снова.")
        return
    payments = payments_data.get("payments", [])

    if not users or not predictions:
        st.info("Загрузите данные для отображения статистики")
        return

    df_users = pd.DataFrame(users)
    df_pred = pd.DataFrame(predictions)
    if df_pred.empty:
        st.info("Нет данных для статистики")
        return

    df_pred["created_at"] = pd.to_datetime(df_pred["created_at"])
    df_payments = pd.DataFrame(payments) if payments else pd.DataFrame()

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Всего пользователей", len(df_users))
    with col2:
        st.metric("Всего предсказаний", len(df_pred))
    with col3:
        avg_per_user = len(df_pred) / len(df_users) if len(df_users) > 0 else 0
        st.metric("Среднее предсказаний на пользователя", f"{avg_per_user:.1f}")
    with col4:
        st.metric("Общий доход (кредиты)", int(df_pred["credits_spent"].sum()))
    with col5:
        credited_payments = 0
        if not df_payments.empty:
            credited_payments = int(df_payments[df_payments["status"] == "confirmed"]["amount"].sum())
        st.metric("Начисленные кредиты", credited_payments)

    st.subheader("Топ пользователей по активности")
    user_activity = (
        df_pred.groupby("user_id")
        .agg({"id": "count", "credits_spent": "sum"})
        .reset_index()
        .rename(columns={"id": "predictions_count", "credits_spent": "total_credits"})
        .sort_values("predictions_count", ascending=False)
        .head(10)
    )
    fig_top = px.bar(
        user_activity,
        x="user_id",
        y="predictions_count",
        title="Топ-10 пользователей по количеству предсказаний",
        labels={"user_id": "User ID", "predictions_count": "Количество предсказаний"},
    )
    st.plotly_chart(fig_top, use_container_width=True)

    st.subheader("Активность по часам")
    df_pred["hour"] = df_pred["created_at"].dt.hour
    hourly_activity = df_pred.groupby("hour").size().reset_index(name="count")
    fig_hourly = px.line(
        hourly_activity,
        x="hour",
        y="count",
        title="Распределение предсказаний по часам",
        labels={"hour": "Час", "count": "Количество"},
    )
    st.plotly_chart(fig_hourly, use_container_width=True)

    if "loyalty_tier" in df_users:
        st.subheader("Распределение loyalty tiers")
        tier_counts = df_users["loyalty_tier"].value_counts().reset_index()
        tier_counts.columns = ["tier", "count"]
        fig_tiers = px.bar(
            tier_counts,
            x="tier",
            y="count",
            title="Пользователи по loyalty tier",
            labels={"tier": "Tier", "count": "Пользователи"},
        )
        st.plotly_chart(fig_tiers, use_container_width=True)
