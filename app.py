"""
InsightSphere — entry point.

    python -m streamlit run app.py

Sets up the page, theme CSS, navigation and the shared sidebar, then runs the
selected page from views/.
"""

import streamlit as st

from core import state
from ui import components as ui
from ui import shell

st.set_page_config(
    page_title="InsightSphere",
    page_icon="ui/assets/logo.svg",
    layout="wide",
    initial_sidebar_state="expanded",
)

shell.inject_css()
shell.logo()


def _coming_soon(title: str):
    """Placeholder page for views that land in a later build phase."""
    def render():
        ui.page_header(title, "Part of the next build phase.")
        st.space("small")
        ui.empty_state(
            f"{title} is being rebuilt",
            "The design system and data foundation are in place; this view is built next.",
            icon_name="chart",
        )
    render.__name__ = "page_" + title.lower().replace(" ", "_")
    return render


PAGES = {
    "Analytics": [
        st.Page("views/overview.py", title="Overview", icon=":material/space_dashboard:",
                url_path="overview", default=True),
        st.Page("views/sales.py", title="Sales", icon=":material/sell:", url_path="sales"),
        st.Page("views/customers.py", title="Customers", icon=":material/group:", url_path="customers"),
        st.Page("views/regions.py", title="Regions", icon=":material/public:", url_path="regions"),
        st.Page("views/operations.py", title="Operations", icon=":material/local_shipping:",
                url_path="operations"),
    ],
    "Intelligence": [
        st.Page(_coming_soon("Forecast"), title="Forecast", icon=":material/insights:", url_path="forecast"),
        st.Page(_coming_soon("Assistant"), title="Assistant", icon=":material/auto_awesome:", url_path="assistant"),
    ],
    "Data": [
        st.Page("views/data.py", title="Data", icon=":material/database:", url_path="data"),
        st.Page(_coming_soon("Forecast runs"), title="Forecast runs", icon=":material/history:",
                url_path="forecast-runs"),
    ],
}

page = st.navigation(PAGES, position="sidebar")

page_paths = ["/"] + ["/" + p.url_path for section in PAGES.values() for p in section]
shell.sidebar(state.get_dataset(), page_paths)

page.run()
