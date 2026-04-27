"""Shared pytest fixtures for backend tests."""
import tempfile
from pathlib import Path
import pytest

import backend.database.connection as db_module
from backend.database.connection import init_database

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def temp_db():
    """Create an isolated temp SQLite DB for one test, fully initialized."""
    original_db = db_module.DB_FILE
    temp_dir = tempfile.mkdtemp()
    temp_db_path = Path(temp_dir) / "test.db"
    db_module.DB_FILE = temp_db_path
    init_database()
    yield temp_db_path
    if temp_db_path.exists():
        temp_db_path.unlink()
    db_module.DB_FILE = original_db


@pytest.fixture
def flex_xml_minimal():
    """Read the minimal Flex XML fixture (1 trade, 1 position)."""
    return (FIXTURES_DIR / "flex_response_minimal.xml").read_text()


@pytest.fixture
def stub_flex_http(monkeypatch, flex_xml_minimal):
    """Stub the IBKR Flex HTTP layer to return the minimal XML.

    The two functions in fetch_flex_trades.py that hit IBKR are
    request_flex_query (returns a reference code) and fetch_flex_results
    (returns XML). We stub both so tests are hermetic.
    """
    import backend.scripts.fetch_flex_trades as flex
    monkeypatch.setattr(flex, "request_flex_query", lambda token, qid: "REF123")
    monkeypatch.setattr(flex, "fetch_flex_results", lambda token, ref: flex_xml_minimal)
    return flex_xml_minimal
