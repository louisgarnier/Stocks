import csv, io
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from backend.api.utils.logger import logger
from backend.database.connection import get_db_connection

router = APIRouter(prefix="/api/screener", tags=["screener"])


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
