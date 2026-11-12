"""The app starts empty: nothing is analysed until data is uploaded (or the sample is chosen)."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def markdown_text(at: AppTest) -> str:
    return " ".join(m.value for m in at.markdown)


def run_page(page: str | None = None, digest: str | None = None) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60)
    if digest:
        at.session_state["active_dataset_digest"] = digest
    at.run()
    if page:
        at.switch_page(page)
        at.run()
    assert not at.exception, at.exception
    return at


def test_landing_page_starts_without_numbers():
    text = markdown_text(run_page())
    assert "waiting for your file" in text
    assert "Live preview" not in text and "$" not in text


def test_analysis_pages_ask_for_an_upload_first():
    for page in ("views/overview.py", "views/sales.py", "views/forecast.py"):
        text = markdown_text(run_page(page))
        assert "Upload your data to get started" in text, page
        assert "is-kpi" not in text, page


def test_choosing_data_fills_the_overview():
    text = markdown_text(run_page("views/overview.py", digest="sample"))
    assert "Upload your data to get started" not in text
    assert "is-kpi" in text and "$733.2K" in text
