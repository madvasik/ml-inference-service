import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json

# Конфигурация страницы
st.set_page_config(
    page_title="ML Service Admin Panel",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Определение BASE_URL в зависимости от окружения
import os
BASE_URL = os.getenv("BASE_URL", "http://backend:8000")  # Внутри Docker сети
# Для локального запуска: BASE_URL = "http://localhost:8000"


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
    """Получение транзакций пользователя"""
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/billing/transactions",
            headers=get_headers(),
            timeout=5
        )
        if response.status_code == 200:
            return response.json()
        return {'transactions': [], 'total': 0}
    except Exception as e:
        st.error(f"Ошибка получения транзакций: {str(e)}")
        return {'transactions': [], 'total': 0}


def main():
    init_session_state()
    
    # Боковая панель для входа
    with st.sidebar:
        st.title("🔐 Вход")
        
        if st.session_state.token is None:
            email = st.text_input("Email", value="demo@example.com")
            password = st.text_input("Пароль", type="password", value="demo123")
            
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
    tab1, tab2, tab3, tab4 = st.tabs(["👥 Пользователи", "🔮 Предсказания", "💰 Транзакции", "📈 Статистика"])
    
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
                regular_users = len(df_users[df_users['role'] == 'user'])
                st.metric("Обычных пользователей", regular_users)
            
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
                df_users[['id', 'email', 'role', 'created_at']],
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
            filter_user_id = st.number_input("Фильтр по User ID", min_value=1, value=None, step=1)
        with col2:
            filter_model_id = st.number_input("Фильтр по Model ID", min_value=1, value=None, step=1)
        
        predictions_data = fetch_predictions(
            user_id=int(filter_user_id) if filter_user_id else None,
            model_id=int(filter_model_id) if filter_model_id else None
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
                        'credits_spent': int(selected_pred['credits_spent'])
                    })
        else:
            st.warning("Предсказания не найдены")
    
    with tab3:
        st.header("Транзакции")
        
        transactions_data = fetch_transactions()
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
    
    with tab4:
        st.header("Общая статистика")
        
        users = fetch_users()
        predictions_data = fetch_predictions()
        predictions = predictions_data.get('predictions', [])
        
        if users and predictions:
            df_users = pd.DataFrame(users)
            df_pred = pd.DataFrame(predictions)
            
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
            else:
                st.info("Нет данных для статистики")
        else:
            st.info("Загрузите данные для отображения статистики")


if __name__ == "__main__":
    main()
