import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import os

# Конфигурация страницы
st.set_page_config(
    page_title="ML Service Admin Panel",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE_URL = os.getenv("BASE_URL", "http://backend:8000")  # Внутри Docker сети
DEFAULT_ADMIN_EMAIL = os.getenv("INITIAL_ADMIN_EMAIL", "admin@mlservice.com")
DEFAULT_ADMIN_PASSWORD = os.getenv("INITIAL_ADMIN_PASSWORD", "admin123")


def init_session_state():
    """Инициализация состояния сессии"""
    if 'token' not in st.session_state:
        st.session_state.token = None
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'is_admin' not in st.session_state:
        st.session_state.is_admin = False


def login(email: str, password: str) -> bool:
    """Вход в систему"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={"email": email, "password": password},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            st.session_state.token = data["access_token"]
            
            # Получаем информацию о пользователе
            headers = {"Authorization": f"Bearer {st.session_state.token}"}
            user_response = requests.get(
                f"{BASE_URL}/api/v1/users/me",
                headers=headers,
                timeout=5
            )
            if user_response.status_code == 200:
                st.session_state.user = user_response.json()
                st.session_state.is_admin = st.session_state.user.get('role') == 'admin'
                return True
        return False
    except Exception as e:
        st.error(f"Ошибка подключения к API: {str(e)}")
        return False


def get_headers():
    """Получение заголовков с токеном"""
    return {"Authorization": f"Bearer {st.session_state.token}"}


def fetch_users():
    """Получение списка всех пользователей"""
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/admin/users",
            headers=get_headers(),
            timeout=5
        )
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        st.error(f"Ошибка получения пользователей: {str(e)}")
        return []


def fetch_predictions(user_id: int = None, model_id: int = None):
    """Получение списка предсказаний"""
    try:
        params = {}
        if user_id:
            params['user_id'] = user_id
        if model_id:
            params['model_id'] = model_id
        
        response = requests.get(
            f"{BASE_URL}/api/v1/admin/predictions",
            headers=get_headers(),
            params=params,
            timeout=5
        )
        if response.status_code == 200:
            return response.json()
        return {'predictions': [], 'total': 0}
    except Exception as e:
        st.error(f"Ошибка получения предсказаний: {str(e)}")
        return {'predictions': [], 'total': 0}


def fetch_transactions(user_id: int = None):
    """Получение транзакций (для админа - все транзакции)"""
    try:
        params = {}
        if user_id:
            params['user_id'] = user_id
        
        # Используем админский endpoint для получения всех транзакций
        response = requests.get(
            f"{BASE_URL}/api/v1/admin/transactions",
            headers=get_headers(),
            params=params,
            timeout=5
        )
        if response.status_code == 200:
            return response.json()
        return {'transactions': [], 'total': 0}
    except Exception as e:
        st.error(f"Ошибка получения транзакций: {str(e)}")
        return {'transactions': [], 'total': 0}


def fetch_payments(user_id: int = None):
    """Получение платежей (для админа - все платежи)."""
    try:
        params = {}
        if user_id:
            params["user_id"] = user_id

        response = requests.get(
            f"{BASE_URL}/api/v1/admin/payments",
            headers=get_headers(),
            params=params,
            timeout=5
        )
        if response.status_code == 200:
            return response.json()
        return {"payments": [], "total": 0}
    except Exception as e:
        st.error(f"Ошибка получения платежей: {str(e)}")
        return {"payments": [], "total": 0}


def main():
    init_session_state()
    
    # Боковая панель для входа
    with st.sidebar:
        st.title("🔐 Вход")
        
        if st.session_state.token is None:
            email = st.text_input("Email", value=DEFAULT_ADMIN_EMAIL)
            password = st.text_input("Пароль", type="password", value=DEFAULT_ADMIN_PASSWORD)
            
            if st.button("Войти", type="primary"):
                if login(email, password):
                    st.success("Вход выполнен!")
                    st.rerun()
                else:
                    st.error("Неверный email или пароль")
        else:
            st.success(f"Вход выполнен как: {st.session_state.user['email']}")
            st.info(f"Роль: {st.session_state.user['role']}")
            
            if st.button("Выйти"):
                st.session_state.token = None
                st.session_state.user = None
                st.session_state.is_admin = False
                st.rerun()
    
    # Основной контент
    if st.session_state.token is None:
        st.title("ML Service Admin Panel")
        st.info("Пожалуйста, войдите в систему через боковую панель")
        return
    
    if not st.session_state.is_admin:
        st.error("⚠️ У вас нет прав администратора для доступа к этой панели")
        st.info("Обратитесь к администратору для получения доступа")
        return
    
    # Главная панель администратора
    st.title("📊 ML Service Admin Panel")
    
    # Вкладки
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["👥 Пользователи", "🔮 Предсказания", "💳 Платежи", "💰 Транзакции", "📈 Статистика"])
    
    with tab1:
        st.header("Список всех пользователей")
        
        users = fetch_users()
        if users:
            df_users = pd.DataFrame(users)
            df_users['created_at'] = pd.to_datetime(df_users['created_at'])
            
            # Метрики
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Всего пользователей", len(df_users))
            with col2:
                admins = len(df_users[df_users['role'] == 'admin'])
                st.metric("Администраторов", admins)
            with col3:
                gold_users = len(df_users[df_users['loyalty_tier'] == 'gold']) if 'loyalty_tier' in df_users else 0
                st.metric("Gold пользователей", gold_users)
            
            # График регистраций по датам
            if len(df_users) > 0:
                df_users['date'] = df_users['created_at'].dt.date
                registrations = df_users.groupby('date').size().reset_index(name='count')
                fig = px.line(registrations, x='date', y='count', 
                             title='Регистрации пользователей по датам',
                             labels={'date': 'Дата', 'count': 'Количество'})
                st.plotly_chart(fig, use_container_width=True)
            
            # Таблица пользователей
            st.subheader("Детальная информация")
            st.dataframe(
                df_users[['id', 'email', 'role', 'loyalty_tier', 'loyalty_discount_percent', 'created_at']],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("Пользователи не найдены")
    
    with tab2:
        st.header("Все предсказания")
        
        # Фильтры
        col1, col2 = st.columns(2)
        with col1:
            filter_user_id = st.number_input(
                "Фильтр по User ID", 
                min_value=0, 
                value=0, 
                step=1,
                help="Введите User ID для фильтрации (0 = без фильтра)"
            )
        with col2:
            filter_model_id = st.number_input(
                "Фильтр по Model ID", 
                min_value=0, 
                value=0, 
                step=1,
                help="Введите Model ID для фильтрации (0 = без фильтра)"
            )
        
        predictions_data = fetch_predictions(
            user_id=int(filter_user_id) if filter_user_id > 0 else None,
            model_id=int(filter_model_id) if filter_model_id > 0 else None
        )
        
        predictions = predictions_data.get('predictions', [])
        total = predictions_data.get('total', 0)
        
        if predictions:
            df_pred = pd.DataFrame(predictions)
            df_pred['created_at'] = pd.to_datetime(df_pred['created_at'])
            
            # Метрики
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Всего предсказаний", total)
            with col2:
                completed = len(df_pred[df_pred['status'] == 'completed'])
                st.metric("Успешных", completed)
            with col3:
                failed = len(df_pred[df_pred['status'] == 'failed'])
                st.metric("Неудачных", failed)
            with col4:
                total_credits = df_pred['credits_spent'].sum()
                st.metric("Всего кредитов потрачено", total_credits)
            with st.container():
                total_discount = df_pred['discount_amount'].sum() if 'discount_amount' in df_pred else 0
                st.metric("Суммарная скидка", total_discount)
            
            # Графики
            col1, col2 = st.columns(2)
            
            with col1:
                # Статусы предсказаний
                status_counts = df_pred['status'].value_counts()
                fig_status = px.pie(
                    values=status_counts.values,
                    names=status_counts.index,
                    title="Распределение по статусам"
                )
                st.plotly_chart(fig_status, use_container_width=True)
            
            with col2:
                # Предсказания по времени
                df_pred['date'] = df_pred['created_at'].dt.date
                pred_by_date = df_pred.groupby('date').size().reset_index(name='count')
                fig_time = px.bar(
                    pred_by_date,
                    x='date',
                    y='count',
                    title="Предсказания по датам",
                    labels={'date': 'Дата', 'count': 'Количество'}
                )
                st.plotly_chart(fig_time, use_container_width=True)
            
            # Таблица предсказаний
            st.subheader("Детальная информация")
            display_cols = ['id', 'user_id', 'model_id', 'status', 'credits_spent', 'created_at']
            st.dataframe(
                df_pred[display_cols],
                use_container_width=True,
                hide_index=True
            )
            
            # Детали конкретного предсказания
            if len(df_pred) > 0:
                selected_id = st.selectbox(
                    "Выберите предсказание для детального просмотра",
                    df_pred['id'].tolist()
                )
                selected_pred = df_pred[df_pred['id'] == selected_id].iloc[0]
                
                with st.expander(f"Детали предсказания #{selected_id}"):
                    st.json({
                        'input_data': json.loads(str(selected_pred['input_data'])) if isinstance(selected_pred['input_data'], str) else selected_pred['input_data'],
                        'result': json.loads(str(selected_pred['result'])) if isinstance(selected_pred['result'], str) else selected_pred['result'],
                        'status': selected_pred['status'],
                        'base_cost': int(selected_pred['base_cost']),
                        'discount_percent': int(selected_pred['discount_percent']),
                        'discount_amount': int(selected_pred['discount_amount']),
                        'credits_spent': int(selected_pred['credits_spent']),
                        'failure_reason': selected_pred.get('failure_reason')
                    })
        else:
            st.warning("Предсказания не найдены")
    
    with tab3:
        st.header("Платежи")

        payments_data = fetch_payments()
        payments = payments_data.get("payments", [])
        total = payments_data.get("total", 0)

        if payments:
            df_payments = pd.DataFrame(payments)
            df_payments["created_at"] = pd.to_datetime(df_payments["created_at"])
            if "confirmed_at" in df_payments:
                df_payments["confirmed_at"] = pd.to_datetime(df_payments["confirmed_at"])

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Всего платежей", total)
            with col2:
                confirmed = len(df_payments[df_payments["status"] == "confirmed"])
                st.metric("Подтвержденных", confirmed)
            with col3:
                paid_credits = df_payments[df_payments["status"] == "confirmed"]["amount"].sum()
                st.metric("Начислено кредитов", paid_credits)

            status_counts = df_payments["status"].value_counts()
            fig_status = px.pie(
                values=status_counts.values,
                names=status_counts.index,
                title="Статусы платежей"
            )
            st.plotly_chart(fig_status, use_container_width=True)

            st.dataframe(
                df_payments[["id", "user_id", "provider", "status", "amount", "external_id", "created_at", "confirmed_at"]],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("Платежи не найдены")

    with tab4:
        st.header("Транзакции")
        
        # Фильтр по User ID
        filter_user_id_trans = st.number_input(
            "Фильтр по User ID", 
            min_value=0, 
            value=0, 
            step=1,
            key="filter_user_id_transactions",
            help="Введите User ID для фильтрации транзакций (0 = без фильтра)"
        )
        
        transactions_data = fetch_transactions(
            user_id=int(filter_user_id_trans) if filter_user_id_trans > 0 else None
        )
        transactions = transactions_data.get('transactions', [])
        total = transactions_data.get('total', 0)
        
        if transactions:
            df_trans = pd.DataFrame(transactions)
            df_trans['created_at'] = pd.to_datetime(df_trans['created_at'])
            
            # Метрики
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Всего транзакций", total)
            with col2:
                credits = df_trans[df_trans['type'] == 'credit']['amount'].sum()
                st.metric("Всего пополнено", f"{credits} кредитов")
            with col3:
                debits = df_trans[df_trans['type'] == 'debit']['amount'].sum()
                st.metric("Всего потрачено", f"{debits} кредитов")
            
            # График транзакций по времени
            df_trans['date'] = df_trans['created_at'].dt.date
            trans_by_date = df_trans.groupby(['date', 'type'])['amount'].sum().reset_index()
            fig_trans = px.bar(
                trans_by_date,
                x='date',
                y='amount',
                color='type',
                title="Транзакции по датам",
                labels={'date': 'Дата', 'amount': 'Сумма (кредиты)', 'type': 'Тип'}
            )
            st.plotly_chart(fig_trans, use_container_width=True)
            
            # Таблица транзакций
            st.subheader("Детальная информация")
            st.dataframe(
                df_trans[['id', 'user_id', 'type', 'amount', 'description', 'created_at']],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("Транзакции не найдены")
    
    with tab5:
        st.header("Общая статистика")
        
        users = fetch_users()
        predictions_data = fetch_predictions()
        predictions = predictions_data.get('predictions', [])
        payments_data = fetch_payments()
        payments = payments_data.get("payments", [])
        
        if users and predictions:
            df_users = pd.DataFrame(users)
            df_pred = pd.DataFrame(predictions)
            df_payments = pd.DataFrame(payments) if payments else pd.DataFrame()
            
            if len(df_pred) > 0:
                df_pred['created_at'] = pd.to_datetime(df_pred['created_at'])
                
                # Общие метрики
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Всего пользователей", len(df_users))
                with col2:
                    st.metric("Всего предсказаний", len(df_pred))
                with col3:
                    avg_per_user = len(df_pred) / len(df_users) if len(df_users) > 0 else 0
                    st.metric("Среднее предсказаний на пользователя", f"{avg_per_user:.1f}")
                with col4:
                    total_revenue = df_pred['credits_spent'].sum()
                    st.metric("Общий доход (кредиты)", total_revenue)
                if len(df_payments) > 0:
                    total_topups = df_payments[df_payments["status"] == "confirmed"]["amount"].sum()
                    st.metric("Подтвержденные top-up", total_topups)
                
                # Топ пользователей по количеству предсказаний
                st.subheader("Топ пользователей по активности")
                user_activity = df_pred.groupby('user_id').agg({
                    'id': 'count',
                    'credits_spent': 'sum'
                }).reset_index()
                user_activity.columns = ['user_id', 'predictions_count', 'total_credits']
                user_activity = user_activity.sort_values('predictions_count', ascending=False).head(10)
                
                fig_top = px.bar(
                    user_activity,
                    x='user_id',
                    y='predictions_count',
                    title="Топ-10 пользователей по количеству предсказаний",
                    labels={'user_id': 'User ID', 'predictions_count': 'Количество предсказаний'}
                )
                st.plotly_chart(fig_top, use_container_width=True)
                
                # Активность по часам
                st.subheader("Активность по часам")
                df_pred['hour'] = df_pred['created_at'].dt.hour
                hourly_activity = df_pred.groupby('hour').size().reset_index(name='count')
                fig_hourly = px.line(
                    hourly_activity,
                    x='hour',
                    y='count',
                    title="Распределение предсказаний по часам",
                    labels={'hour': 'Час', 'count': 'Количество'}
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
                        labels={"tier": "Tier", "count": "Пользователи"}
                    )
                    st.plotly_chart(fig_tiers, use_container_width=True)
            else:
                st.info("Нет данных для статистики")
        else:
            st.info("Загрузите данные для отображения статистики")


if __name__ == "__main__":
    main()
