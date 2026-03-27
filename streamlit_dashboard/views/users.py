import pandas as pd
import plotly.express as px
import streamlit as st

from streamlit_dashboard.api_client import APIClient


def render_users_tab(api_client: APIClient, token: str) -> None:
    st.header("Список всех пользователей")

    users = api_client.fetch_users(token)
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
