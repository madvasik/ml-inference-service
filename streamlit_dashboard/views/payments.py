import pandas as pd
import plotly.express as px
import streamlit as st

from streamlit_dashboard.api_client import APIClient


def render_payments_tab(api_client: APIClient, token: str) -> None:
    st.header("Платежи")

    payments_data = api_client.fetch_payments(token)
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
