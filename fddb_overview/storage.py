"""Lokale Datenhaltung: JSON-Lesen/-Schreiben, Import-Snapshots, Konsolidierung.

Verzeichnislayout (neben der EXE bzw. unter FDDB_DATA_DIR):

    data/days.json            konsolidierte Tagesdaten
    data/products.json        konsolidierter Produktkatalog (abgeleitet)
    data/settings.json        Profil + FDDB-Zugangsdaten
    data/notes.json           Tagesnotizen ("Besonderheiten")
    data/imports/<ts>/...     einzelne Import-Snapshots
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from .model.domain import Day, Product


def get_data_dir() -> Path:
    """Datenordner ermitteln (ueberschreibbar via FDDB_DATA_DIR)."""
    env = os.environ.get("FDDB_DATA_DIR")
    if env:
        base = Path(env)
    else:
        # Neben der ausfuehrbaren Datei bzw. im Projektordner.
        base = Path(os.environ.get("FDDB_BASE_DIR", Path.cwd())) / "data"
    base.mkdir(parents=True, exist_ok=True)
    (base / "imports").mkdir(parents=True, exist_ok=True)
    return base


# ---------------------------------------------------------------------------
# Allgemeine JSON-Helfer
# ---------------------------------------------------------------------------

def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return default


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Tage / Produkte
# ---------------------------------------------------------------------------

def load_days() -> Dict[str, Day]:
    raw = _read_json(get_data_dir() / "days.json", {"days": {}})
    days_raw = raw.get("days", raw) if isinstance(raw, dict) else {}
    out: Dict[str, Day] = {}
    for date, d in days_raw.items():
        if isinstance(d, dict):
            day = Day.from_dict(d)
            day.date = date
            out[date] = day
    return out


def save_days(days: Dict[str, Day]) -> None:
    data = {"days": {date: day.to_dict() for date, day in sorted(days.items())}}
    _write_json(get_data_dir() / "days.json", data)
    # Produktkatalog ableiten und mitschreiben.
    save_products(build_product_catalog(days))


def build_product_catalog(days: Dict[str, Day]) -> dict:
    """Erzeugt aus allen Tagen einen Katalog je Produkt fuer Listen/Suche."""
    catalog: Dict[str, dict] = {}
    for date in sorted(days.keys()):
        day = days[date]
        for p in day.products:
            key = p.link or p.name
            entry = catalog.setdefault(key, {
                "name": p.name,
                "link": p.link,
                "count": 0,
                "total_kcal": 0.0,
                "dates": [],
            })
            entry["count"] += 1
            entry["total_kcal"] = round(entry["total_kcal"] + p.kcal, 1)
            if date not in entry["dates"]:
                entry["dates"].append(date)
    return {"products": catalog}


def save_products(catalog: dict) -> None:
    _write_json(get_data_dir() / "products.json", catalog)


def load_products() -> dict:
    return _read_json(get_data_dir() / "products.json", {"products": {}})


# ---------------------------------------------------------------------------
# Import-Snapshots + Konsolidierung
# ---------------------------------------------------------------------------

def write_snapshot(days: Dict[str, Day], metadata: dict) -> str:
    """Schreibt einen Import-Snapshot und gibt den Zeitstempel-Ordner zurueck."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    folder = get_data_dir() / "imports" / ts
    folder.mkdir(parents=True, exist_ok=True)
    _write_json(folder / "days.json",
                {"days": {d: day.to_dict() for d, day in days.items()}})
    _write_json(folder / "metadata.json", {**metadata, "timestamp": ts})
    return ts


def consolidate(new_days: Dict[str, Day]) -> Dict[str, Day]:
    """Fuehrt neue Tage in die konsolidierte Arbeitsdatei ein.

    Regel (wie im Original): vollstaendige Tage schlagen unvollstaendige;
    bei gleicher Qualitaet gewinnt der spaetere (= neue) Import.
    """
    current = load_days()
    for date, new_day in new_days.items():
        old = current.get(date)
        if old is None:
            current[date] = new_day
            continue
        # Vollstaendigkeit vergleichen.
        if new_day.complete and not old.complete:
            current[date] = new_day
        elif old.complete and not new_day.complete:
            pass  # alten vollstaendigen Tag behalten
        else:
            current[date] = new_day  # gleiche Qualitaet -> neuer gewinnt
    save_days(current)
    return current


def replace_all(new_days: Dict[str, Day]) -> Dict[str, Day]:
    """Manueller Import: ueberschreibt die konsolidierten Arbeitsdateien."""
    save_days(new_days)
    return new_days


# ---------------------------------------------------------------------------
# Einstellungen / Profil / Zugangsdaten
# ---------------------------------------------------------------------------

def load_settings() -> dict:
    return _read_json(get_data_dir() / "settings.json", {
        "name": "",
        "birthdate": "",
        "fddb_username": "",
        "fddb_password": "",
        "fddb_cookie": "",
    })


def save_settings(settings: dict) -> None:
    current = load_settings()
    current.update({k: v for k, v in settings.items() if v is not None})
    _write_json(get_data_dir() / "settings.json", current)


# ---------------------------------------------------------------------------
# Tagesnotizen
# ---------------------------------------------------------------------------

def load_notes() -> dict:
    return _read_json(get_data_dir() / "notes.json", {})


def save_note(date: str, text: str) -> None:
    notes = load_notes()
    if text:
        notes[date] = text
    else:
        notes.pop(date, None)
    _write_json(get_data_dir() / "notes.json", notes)


def get_note(date: str) -> str:
    return load_notes().get(date, "")
