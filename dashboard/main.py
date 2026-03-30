import streamlit as st

try:
    from dashboard.api_client import APIClient
    from dashboard.config import (
        DEFAULT_ADMIN_EMAIL,
        DEFAULT_ADMIN_PASSWORD,
        PAGE_TITLE,
        configure_page,
    )
    from dashboard.views import (
        render_payments_tab,
        render_predictions_tab,
        render_stats_tab,
        render_transactions_tab,
        render_users_tab,
    )
except ModuleNotFoundError:
    from api_client import APIClient
    from config import DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD, PAGE_TITLE, configure_page
    from views import (
        render_payments_tab,
        render_predictions_tab,
        render_stats_tab,
        render_transactions_tab,
        render_users_tab,
    )


def init_session_state() -> None:
    st.session_state.setdefault("token", None)
    st.session_state.setdefault("user", None)
    st.session_state.setdefault("is_admin", False)


def reset_session_state() -> None:
    st.session_state.token = None
    st.session_state.user = None
    st.session_state.is_admin = False


def render_sidebar(api_client: APIClient) -> None:
    with st.sidebar:
        st.title("🔐 Вход")
        if st.session_state.token is None:
            email = st.text_input("Email", value=DEFAULT_ADMIN_EMAIL)
            password = st.text_input("Пароль", type="password", value=DEFAULT_ADMIN_PASSWORD)
            if st.button("Войти", type="primary"):
                success, token, user, error_message = api_client.login(email, password)
                if success and token and user:
                    st.session_state.token = token
                    st.session_state.user = user
                    st.session_state.is_admin = user.get("role") == "admin"
                    st.success("Вход выполнен!")
                    st.rerun()
                st.error(error_message or "Неверный email или пароль")
        else:
            st.success(f"Вход выполнен как: {st.session_state.user['email']}")
            st.info(f"Роль: {st.session_state.user['role']}")
            if st.button("Выйти"):
                reset_session_state()
                st.rerun()


def render_dashboard(api_client: APIClient) -> None:
    if st.session_state.token is None:
        st.title(PAGE_TITLE)
        st.info("Пожалуйста, войдите в систему через боковую панель")
        return

    if not st.session_state.is_admin:
        st.error("⚠️ У вас нет прав администратора для доступа к этой панели")
        st.info("Обратитесь к администратору для получения доступа")
        return

    st.title(PAGE_TITLE)
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["👥 Пользователи", "🔮 Предсказания", "💳 Платежи", "💰 Транзакции", "📈 Статистика"]
    )

    with tab1:
        render_users_tab(api_client, st.session_state.token)
    with tab2:
        render_predictions_tab(api_client, st.session_state.token)
    with tab3:
        render_payments_tab(api_client, st.session_state.token)
    with tab4:
        render_transactions_tab(api_client, st.session_state.token)
    with tab5:
        render_stats_tab(api_client, st.session_state.token)


def main() -> None:
    configure_page()
    init_session_state()
    api_client = APIClient()
    render_sidebar(api_client)
    render_dashboard(api_client)


if __name__ == "__main__":
    main()
