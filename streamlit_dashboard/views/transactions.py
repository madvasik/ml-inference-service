import pandas as pd
import plotly.express as px
import streamlit as st

from streamlit_dashboard.api_client import APIClient


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
    transactions_data = api_client.fetch_transactions(
        token,
        user_id=int(filter_user_id) if filter_user_id > 0 else None,
    )
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
