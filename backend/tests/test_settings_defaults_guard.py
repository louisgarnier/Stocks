"""Guard against DEFAULTS dicts (used to merge over drifted/missing DB rows in
screener_settings) silently falling behind the authoritative seed in
backend/database/schema.sql.

If schema.sql gains a new key in one of these seeds and nobody updates the
matching module-level DEFAULTS dict, this test fails loudly instead of the
loader quietly missing the new key on a partial/missing row.
"""
import json
import re
from pathlib import Path

from backend.scripts.consolidation_core import CONSOLIDATION_DEFAULTS
from backend.scripts.fundamentals_fetch import QUALITY_GATES_DEFAULTS
from backend.scripts.scoring_compute import SCORING_WEIGHTS_DEFAULTS
from backend.api.routes.sync import RETENTION_DEFAULTS

SCHEMA_SQL = Path(__file__).resolve().parents[1] / "database" / "schema.sql"


def _seed_json_for_key(key: str) -> dict:
    """Parse the JSON literal seeded for `key` in the screener_settings
    INSERT OR IGNORE block of schema.sql."""
    text = SCHEMA_SQL.read_text()
    # Matches: ('<key>', '<json>', ...)
    m = re.search(r"\('" + re.escape(key) + r"',\s*'(\{.*?\})'", text)
    assert m, f"could not find seed row for key={key!r} in schema.sql"
    return json.loads(m.group(1))


def test_consolidation_defaults_cover_schema_seed():
    seed = _seed_json_for_key("consolidation_params")
    assert set(seed).issubset(set(CONSOLIDATION_DEFAULTS))


def test_quality_gates_defaults_cover_schema_seed():
    seed = _seed_json_for_key("quality_gates")
    assert set(seed).issubset(set(QUALITY_GATES_DEFAULTS))


def test_scoring_weights_defaults_cover_schema_seed():
    seed = _seed_json_for_key("scoring_weights")
    assert set(seed).issubset(set(SCORING_WEIGHTS_DEFAULTS))


def test_retention_defaults_cover_schema_seed():
    seed = _seed_json_for_key("retention")
    assert set(seed).issubset(set(RETENTION_DEFAULTS))
