import json

import pandas as pd
import plotly.express as px
import streamlit as st

from streamlit_dashboard.api_client import APIClient


def _parse_jsonish(value):
    if isinstance(value, str):
        return json.loads(value)
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

    predictions_data = api_client.fetch_predictions(
        token,
        user_id=int(filter_user_id) if filter_user_id > 0 else None,
        model_id=int(filter_model_id) if filter_model_id > 0 else None,
    )
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
