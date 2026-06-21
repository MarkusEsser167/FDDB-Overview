"""Auswertungs-Services: Tag, Datumsbereich, Listen, Aggregationen.

Operiert auf den konsolidierten Daten aus dem storage-Modul und liefert
JSON-faehige Dictionaries fuer Oberflaeche und Export.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from .. import storage
from ..model.domain import Day, meal_sort_key

WEEKDAYS_DE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag",
               "Freitag", "Samstag", "Sonntag"]
MONTHS_DE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
             "August", "September", "Oktober", "November", "Dezember"]


def _round(x: float) -> float:
    return round(x or 0.0, 1)


# ---------------------------------------------------------------------------
# Einzelner Tag
# ---------------------------------------------------------------------------

def get_day(date_iso: str) -> Optional[dict]:
    days = storage.load_days()
    day = days.get(date_iso)
    if day is None:
        return None
    return _day_view(day)


def _day_view(day: Day) -> dict:
    return {
        "date": day.date,
        "weekday": _weekday_name(day.date),
        "complete": day.complete,
        "meals": day.meals(),
        "totals": day.totals.to_dict(),
        "note": storage.get_note(day.date),
        "copy_text": _day_copy_text(day),
    }


def _weekday_name(date_iso: str) -> str:
    try:
        return WEEKDAYS_DE[datetime.strptime(date_iso, "%Y-%m-%d").weekday()]
    except ValueError:
        return ""


def _day_copy_text(day: Day) -> str:
    lines = [f"{_weekday_name(day.date)}, {day.date}"]
    for meal in day.meals():
        lines.append(f"\n{meal['name']} ({_round(meal['kcal'])} kcal)")
        for p in meal["products"]:
            lines.append(
                f"  - {p['amount']} {p['name']}: "
                f"{_round(p['kcal'])} kcal, F {_round(p['fat'])}g, "
                f"KH {_round(p['carbs'])}g, EW {_round(p['protein'])}g"
            )
    t = day.totals
    lines.append(
        f"\nTagessumme: {_round(t.kcal)} kcal, F {_round(t.fat)}g, "
        f"KH {_round(t.carbs)}g, EW {_round(t.protein)}g"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Datumsbereich
# ---------------------------------------------------------------------------

def get_range(from_iso: str, to_iso: str) -> dict:
    days = storage.load_days()
    start = datetime.strptime(from_iso, "%Y-%m-%d").date()
    end = datetime.strptime(to_iso, "%Y-%m-%d").date()
    if end < start:
        start, end = end, start

    selected: List[Day] = []
    cur = start
    while cur <= end:
        iso = cur.isoformat()
        if iso in days:
            selected.append(days[iso])
        cur += timedelta(days=1)

    day_views = [_day_view(d) for d in selected]
    totals = _sum_totals(selected)
    return {
        "from": from_iso,
        "to": to_iso,
        "count": len(selected),
        "days": day_views,
        "totals": totals,
        "averages": {k: _round(v / len(selected)) if selected else 0.0
                     for k, v in totals.items()},
        "day_copy_text": "\n\n".join(d["copy_text"] for d in day_views),
        "meal_copy_text": _range_meal_copy_text(selected),
    }


def _sum_totals(days: List[Day]) -> dict:
    return {
        "kcal": _round(sum(d.totals.kcal for d in days)),
        "fat": _round(sum(d.totals.fat for d in days)),
        "carbs": _round(sum(d.totals.carbs for d in days)),
        "protein": _round(sum(d.totals.protein for d in days)),
        "sugar": _round(sum(d.totals.sugar or 0 for d in days)),
        "fiber": _round(sum(d.totals.fiber or 0 for d in days)),
    }


def _range_meal_copy_text(days: List[Day]) -> str:
    lines = []
    for day in days:
        for meal in day.meals():
            names = ", ".join(p["name"] for p in meal["products"])
            lines.append(f"{day.date} {meal['name']}: {names}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Listen: Produktsuche, Top-100, Tagesranking
# ---------------------------------------------------------------------------

def search_products(query: str = "", weekdays: Optional[List[int]] = None) -> List[dict]:
    """Sucht Produkte und liefert Verzehrtage (optional auf Wochentage gefiltert)."""
    days = storage.load_days()
    q = (query or "").strip().lower()
    result: Dict[str, dict] = {}
    for iso in sorted(days.keys()):
        wd = datetime.strptime(iso, "%Y-%m-%d").weekday()
        if weekdays and wd not in weekdays:
            continue
        for p in days[iso].products:
            if q and q not in p.name.lower():
                continue
            key = p.link or p.name
            entry = result.setdefault(key, {
                "name": p.name, "link": p.link,
                "count": 0, "total_kcal": 0.0, "dates": [],
            })
            entry["count"] += 1
            entry["total_kcal"] = _round(entry["total_kcal"] + p.kcal)
            if iso not in entry["dates"]:
                entry["dates"].append(iso)
    return sorted(result.values(), key=lambda e: e["count"], reverse=True)


def top_products(limit: int = 100) -> List[dict]:
    return search_products()[:limit]


def product_dates(name_or_link: str) -> dict:
    """Alle Tage, an denen ein bestimmtes Produkt verzehrt wurde."""
    days = storage.load_days()
    key = name_or_link.strip().lower()
    hits = []
    for iso in sorted(days.keys()):
        for p in days[iso].products:
            if key in (p.link or "").lower() or key == p.name.lower():
                hits.append({"date": iso, "amount": p.amount, "meal": p.meal,
                             "kcal": _round(p.kcal)})
    name = hits[0] if hits else None
    return {"query": name_or_link, "entries": hits, "count": len(hits)}


def day_ranking(metric: str = "kcal", limit: int = 100) -> List[dict]:
    """Tagesranking nach kcal/Fett/KH/Eiweiss."""
    days = storage.load_days()
    rows = []
    for iso, day in days.items():
        t = day.totals
        value = {"kcal": t.kcal, "fat": t.fat, "carbs": t.carbs,
                 "protein": t.protein}.get(metric, t.kcal)
        rows.append({"date": iso, "weekday": _weekday_name(iso),
                     "value": _round(value), "kcal": _round(t.kcal)})
    rows.sort(key=lambda r: r["value"], reverse=True)
    return rows[:limit]


# ---------------------------------------------------------------------------
# Aggregationen: Mahlzeit, Wochentag, Monat
# ---------------------------------------------------------------------------

def aggregate_by_meal() -> List[dict]:
    days = storage.load_days()
    groups: Dict[str, dict] = {}
    for day in days.values():
        for meal in day.meals():
            g = groups.setdefault(meal["name"], _empty_group(meal["name"]))
            g["count"] += 1
            g["kcal"] += meal["kcal"]
            g["fat"] += meal["fat"]
            g["carbs"] += meal["carbs"]
            g["protein"] += meal["protein"]
    return _finalize_groups(groups, sort_key=lambda g: meal_sort_key(g["label"]))


def aggregate_by_weekday() -> List[dict]:
    days = storage.load_days()
    groups: Dict[int, dict] = {}
    for iso, day in days.items():
        wd = datetime.strptime(iso, "%Y-%m-%d").weekday()
        g = groups.setdefault(wd, _empty_group(WEEKDAYS_DE[wd]))
        _add_day_totals(g, day)
    ordered = [groups[i] for i in range(7) if i in groups]
    return _finalize_list(ordered)


def aggregate_by_month() -> List[dict]:
    days = storage.load_days()
    groups: Dict[str, dict] = {}
    for iso, day in days.items():
        dt = datetime.strptime(iso, "%Y-%m-%d")
        label = f"{MONTHS_DE[dt.month - 1]} {dt.year}"
        key = f"{dt.year}-{dt.month:02d}"
        g = groups.setdefault(key, _empty_group(label))
        _add_day_totals(g, day)
    ordered = [groups[k] for k in sorted(groups.keys())]
    return _finalize_list(ordered)


def _empty_group(label: str) -> dict:
    return {"label": label, "count": 0, "kcal": 0.0, "fat": 0.0,
            "carbs": 0.0, "protein": 0.0}


def _add_day_totals(g: dict, day: Day) -> None:
    g["count"] += 1
    g["kcal"] += day.totals.kcal
    g["fat"] += day.totals.fat
    g["carbs"] += day.totals.carbs
    g["protein"] += day.totals.protein


def _finalize_groups(groups: dict, sort_key) -> List[dict]:
    return _finalize_list(sorted(groups.values(), key=sort_key))


def _finalize_list(items: List[dict]) -> List[dict]:
    out = []
    for g in items:
        c = g["count"] or 1
        out.append({
            "label": g["label"],
            "count": g["count"],
            "kcal_sum": _round(g["kcal"]),
            "kcal_avg": _round(g["kcal"] / c),
            "fat_avg": _round(g["fat"] / c),
            "carbs_avg": _round(g["carbs"] / c),
            "protein_avg": _round(g["protein"] / c),
        })
    return out


# ---------------------------------------------------------------------------
# Uebersicht / Statistik
# ---------------------------------------------------------------------------

def overview() -> dict:
    days = storage.load_days()
    if not days:
        return {"empty": True, "count": 0}
    isos = sorted(days.keys())
    totals = _sum_totals(list(days.values()))
    return {
        "empty": False,
        "count": len(days),
        "first": isos[0],
        "last": isos[-1],
        "avg_kcal": _round(totals["kcal"] / len(days)),
        "totals": totals,
    }
