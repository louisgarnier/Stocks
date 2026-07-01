import csv, io, json
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from backend.api.utils.logger import logger
from backend.database.connection import get_db_connection
from backend.scripts.consolidation_core import CONSOLIDATION_DEFAULTS

router = APIRouter(prefix="/api/screener", tags=["screener"])

# Editable screener settings and their recommended defaults. GET returns the
# stored value merged over these defaults (seed-drift safe); PUT validates keys
# against the defaults and merges partial updates.
SETTINGS_DEFAULTS = {
    "consolidation_params": CONSOLIDATION_DEFAULTS,
}


class SettingsUpdate(BaseModel):
    params: dict


@router.get("/settings/{key}")
async def get_settings(key: str):
    if key not in SETTINGS_DEFAULTS:
        raise HTTPException(404, f"unknown settings key: {key}")
    defaults = dict(SETTINGS_DEFAULTS[key])
    conn = get_db_connection()
    row = conn.execute("SELECT value_json FROM screener_settings WHERE key=?", (key,)).fetchone()
    conn.close()
    stored = json.loads(row["value_json"]) if row else {}
    return {"key": key, "params": {**defaults, **stored}, "defaults": defaults}


@router.put("/settings/{key}")
async def put_settings(key: str, body: SettingsUpdate):
    if key not in SETTINGS_DEFAULTS:
        raise HTTPException(404, f"unknown settings key: {key}")
    defaults = SETTINGS_DEFAULTS[key]
    unknown = [k for k in body.params if k not in defaults]
    if unknown:
        raise HTTPException(400, f"unknown params: {unknown}")
    conn = get_db_connection()
    row = conn.execute("SELECT value_json FROM screener_settings WHERE key=?", (key,)).fetchone()
    stored = json.loads(row["value_json"]) if row else {}
    merged = {**stored, **body.params}
    conn.execute(
        "INSERT INTO screener_settings (key, value_json) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json",
        (key, json.dumps(merged)),
    )
    conn.commit()
    conn.close()
    logger.info(f"⚙️  Screener settings updated: {key} <- {list(body.params.keys())}")
    return {"key": key, "params": {**dict(defaults), **merged}}


@router.get("/overview")
async def overview(format: str = Query("json", pattern="^(json|csv)$")):
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM screener_overview ORDER BY symbol").fetchall()
    conn.close()
    dicts = [{k: r[k] for k in r.keys()} for r in rows]
    if format == "csv":
        buf = io.StringIO()
        if dicts:
            w = csv.DictWriter(buf, fieldnames=list(dicts[0].keys()))
            w.writeheader(); w.writerows(dicts)
        logger.info(f"📤 Screener overview CSV: {len(dicts)} rows")
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=screener_overview.csv"})
    return {"rows": dicts, "count": len(dicts)}
