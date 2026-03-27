import pandas as pd
import plotly.express as px
import streamlit as st

from streamlit_dashboard.api_client import APIClient


def render_stats_tab(api_client: APIClient, token: str) -> None:
    st.header("Общая статистика")

    users = api_client.fetch_users(token)
    predictions_data = api_client.fetch_predictions(token)
    predictions = predictions_data.get("predictions", [])
    payments_data = api_client.fetch_payments(token)
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
