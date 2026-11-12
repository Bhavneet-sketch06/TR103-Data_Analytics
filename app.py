"""
InsightSphere — entry point.

    python -m streamlit run app.py

Sets up the page, theme CSS, navigation and the shared sidebar, then runs the
selected page from views/.
"""

import streamlit as st

from core import state
from ui import shell

st.set_page_config(
    page_title="InsightSphere",
    page_icon="ui/assets/logo.svg",
    layout="wide",
    initial_sidebar_state="expanded",
)

shell.inject_css()
shell.logo()


PAGES = {
    "": [
        st.Page("views/home.py", title="Home", icon=":material/home:", default=True),
    ],
    "Analytics": [
        st.Page("views/overview.py", title="Overview", icon=":material/space_dashboard:",
                url_path="overview"),
        st.Page("views/sales.py", title="Sales", icon=":material/sell:", url_path="sales"),
        st.Page("views/customers.py", title="Customers", icon=":material/group:", url_path="customers"),
        st.Page("views/regions.py", title="Regions", icon=":material/public:", url_path="regions"),
        st.Page("views/operations.py", title="Operations", icon=":material/local_shipping:",
                url_path="operations"),
    ],
    "Planning": [
        st.Page("views/planning.py", title="Forecast", icon=":material/insights:", url_path="forecast"),
    ],
    "Data": [
        st.Page("views/data.py", title="Data", icon=":material/database:", url_path="data"),
    ],
}

page = st.navigation(PAGES, position="sidebar")

shell.set_page_paths(sorted({"/" + p.url_path for section in PAGES.values() for p in section}))
if page.title != "Home":  # the landing page has no app sidebar
    shell.sidebar(state.get_dataset())

page.run()
