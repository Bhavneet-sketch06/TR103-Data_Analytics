"""Every page renders without errors for very different uploads, or explains what's missing."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import ingest
from core.schema import suggest_mapping

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"
PAGES = ["views/home.py", "views/overview.py", "views/sales.py", "views/customers.py", "views/regions.py",
         "views/operations.py", "views/forecast.py", "views/data.py"]


def upload_digest(name: str) -> str:
    data = (FIXTURES / name).read_bytes()
    cleaned, _ = ingest.read_and_clean(data, name)
    return ingest.save_upload(data, name, suggest_mapping(cleaned.columns))


@pytest.fixture(scope="module", params=["sample", "renamed_schema.csv", "minimal.csv", "messy.csv"])
def digest(request):
    return "sample" if request.param == "sample" else upload_digest(request.param)


@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page, digest):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.session_state["active_dataset_digest"] = digest
    at.run()
    at.switch_page(page)
    at.run()
    assert not at.exception, f"{page}: {at.exception}"
    assert not at.error, f"{page}: {[e.value for e in at.error]}"
