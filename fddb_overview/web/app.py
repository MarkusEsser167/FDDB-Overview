"""FastAPI-Anwendung: REST-API + Auslieferung der Weboberflaeche."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import (FileResponse, HTMLResponse, JSONResponse,
                               Response)
from fastapi.staticfiles import StaticFiles

from .. import storage
from ..model.domain import Day
from ..service import analysis
from ..export import excel_export, pdf_export
from ..sync import sync_service

def _static_dir() -> Path:
    """Findet den static-Ordner auch in der gepackten EXE (PyInstaller)."""
    candidates = [Path(__file__).parent / "static"]
    base = getattr(sys, "_MEIPASS", None)
    if base:
        candidates.insert(0, Path(base) / "fddb_overview" / "web" / "static")
    for c in candidates:
        if c.exists():
            return c
    return candidates[-1]


STATIC_DIR = _static_dir()

app = FastAPI(title="FDDB Overview", version="1.0.0")


# ---------------------------------------------------------------------------
# Oberflaeche
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/help", response_class=HTMLResponse)
def help_page() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "help.html").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Uebersicht / Einstellungen
# ---------------------------------------------------------------------------

@app.get("/api/overview")
def api_overview():
    return analysis.overview()


@app.get("/api/settings")
def api_get_settings():
    s = storage.load_settings()
    # Passwort nicht im Klartext zuruecksenden.
    return {
        "name": s.get("name", ""),
        "birthdate": s.get("birthdate", ""),
        "fddb_username": s.get("fddb_username", ""),
        "has_password": bool(s.get("fddb_password")),
        "has_cookie": bool(s.get("fddb_cookie")),
    }


@app.post("/api/settings")
async def api_save_settings(request: Request):
    data = await request.json()
    storage.save_settings({
        "name": data.get("name"),
        "birthdate": data.get("birthdate"),
        "fddb_username": data.get("fddb_username"),
        "fddb_password": data.get("fddb_password") or None,
        "fddb_cookie": data.get("fddb_cookie"),
    })
    return {"ok": True}


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------

@app.get("/api/sync/suggest")
def api_sync_suggest():
    return sync_service.suggest_timeframe()


@app.post("/api/sync/start")
async def api_sync_start(request: Request):
    data = await request.json()
    if sync_service.progress.snapshot()["running"]:
        raise HTTPException(409, "Es laeuft bereits ein Sync.")
    sync_service.run_sync_async(
        data["from"], data["to"],
        username=data.get("username", ""),
        password=data.get("password", ""),
        cookie=data.get("cookie", ""),
    )
    return {"ok": True}


@app.get("/api/sync/progress")
def api_sync_progress():
    return sync_service.progress.snapshot()


# ---------------------------------------------------------------------------
# Manueller JSON-Import
# ---------------------------------------------------------------------------

@app.post("/api/import")
async def api_import(request: Request):
    data = await request.json()
    days_raw = data.get("days")
    if isinstance(days_raw, dict) and "days" in days_raw:
        days_raw = days_raw["days"]
    if not isinstance(days_raw, dict):
        raise HTTPException(400, "Erwarte ein Objekt mit Tagesdaten.")
    days = {iso: Day.from_dict({**d, "date": iso}) for iso, d in days_raw.items()}
    storage.replace_all(days)
    return {"ok": True, "count": len(days)}


# ---------------------------------------------------------------------------
# Auswertungen
# ---------------------------------------------------------------------------

@app.get("/api/day/{date_iso}")
def api_day(date_iso: str):
    day = analysis.get_day(date_iso)
    if day is None:
        raise HTTPException(404, "Kein Tag mit diesem Datum.")
    return day


@app.get("/api/range")
def api_range(date_from: str, date_to: str):
    return analysis.get_range(date_from, date_to)


@app.get("/api/list/search")
def api_search(q: str = "", weekdays: str = ""):
    wd = [int(x) for x in weekdays.split(",") if x.strip().isdigit()] or None
    return analysis.search_products(q, wd)


@app.get("/api/list/top")
def api_top(limit: int = 100):
    return analysis.top_products(limit)


@app.get("/api/list/product")
def api_product(key: str):
    return analysis.product_dates(key)


@app.get("/api/list/ranking")
def api_ranking(metric: str = "kcal", limit: int = 100):
    return analysis.day_ranking(metric, limit)


@app.get("/api/aggregate/{kind}")
def api_aggregate(kind: str):
    if kind == "meal":
        return analysis.aggregate_by_meal()
    if kind == "weekday":
        return analysis.aggregate_by_weekday()
    if kind == "month":
        return analysis.aggregate_by_month()
    raise HTTPException(404, "Unbekannte Aggregation.")


# ---------------------------------------------------------------------------
# Tagesnotizen
# ---------------------------------------------------------------------------

@app.post("/api/note")
async def api_note(request: Request):
    data = await request.json()
    storage.save_note(data["date"], data.get("text", ""))
    return {"ok": True}


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@app.get("/api/export/excel")
def api_export_excel(date: Optional[str] = None,
                     date_from: Optional[str] = None,
                     date_to: Optional[str] = None):
    if date:
        content = excel_export.export_single_day(date)
        fname = f"fddb_{date}.xlsx"
    else:
        content = excel_export.export_range(date_from, date_to)
        fname = f"fddb_{date_from}_bis_{date_to}.xlsx"
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@app.get("/api/export/pdf")
def api_export_pdf(date: Optional[str] = None,
                   date_from: Optional[str] = None,
                   date_to: Optional[str] = None):
    if date:
        content = pdf_export.export_single_day(date)
        fname = f"fddb_{date}.pdf"
    