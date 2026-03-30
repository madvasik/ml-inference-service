import os

import streamlit as st


PAGE_TITLE = "ML Service Admin Panel"
PAGE_ICON = "📊"
LAYOUT = "wide"
SIDEBAR_STATE = "expanded"
BASE_URL = os.getenv("BASE_URL", "http://backend:8000")
DEFAULT_ADMIN_EMAIL = os.getenv("INITIAL_ADMIN_EMAIL", "")
DEFAULT_ADMIN_PASSWORD = os.getenv("INITIAL_ADMIN_PASSWORD", "")
API_TIMEOUT_SECONDS = 5


def configure_page() -> None:
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon=PAGE_ICON,
        layout=LAYOUT,
        initial_sidebar_state=SIDEBAR_STATE,
    )
