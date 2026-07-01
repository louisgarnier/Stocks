"""R-2: read/write consolidation params so they're tunable from the app."""
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)


def test_get_consolidation_params_merges_defaults(temp_db):
    r = client.get("/api/screener/settings/consolidation_params")
    assert r.status_code == 200
    body = r.json()
    # merged params include the new tunable gates at their recommended defaults
    assert body["params"]["min_pct_in_channel"] == 70.0
    assert body["params"]["max_consolidation_range_pct"] == 5.0
    # defaults block is exposed so the UI can show "recommended" + reset
    assert body["defaults"]["min_pct_in_channel"] == 70.0


def test_put_updates_param_and_merges(temp_db):
    r = client.put(
        "/api/screener/settings/consolidation_params",
        json={"params": {"max_consolidation_range_pct": 12.0, "min_pct_in_channel": 45.0}},
    )
    assert r.status_code == 200
    got = client.get("/api/screener/settings/consolidation_params").json()["params"]
    assert got["max_consolidation_range_pct"] == 12.0
    assert got["min_pct_in_channel"] == 45.0
    # untouched keys keep their defaults (merge, not replace)
    assert got["min_boundary_touches"] == 4


def test_put_rejects_unknown_key(temp_db):
    r = client.put(
        "/api/screener/settings/consolidation_params",
        json={"params": {"totally_bogus_param": 1}},
    )
    assert r.status_code == 400
