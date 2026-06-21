"""Tests fuer Storage-Konsolidierung und Auswertungen (mit Temp-Datenordner)."""
import os
import tempfile
from datetime import date

import pytest

from fddb_overview import storage
from fddb_overview.model.domain import Day, DayTotals, Product
from fddb_overview.service import analysis


@pytest.fixture(autouse=True)
def temp_data(monkeypatch):
    d = tempfile.mkdtemp()
    monkeypatch.setenv("FDDB_DATA_DIR", d)
    yield d


def _day(iso, products, complete=True):
    day = Day(date=iso, products=products, complete=complete)
    day.totals = DayTotals(
        kcal=sum(p.kcal for p in products),
        fat=sum(p.fat for p in products),
        carbs=sum(p.carbs for p in products),
        protein=sum(p.protein for p in products),
    )
    return day


def test_consolidate_complete_beats_incomplete():
    p = Product(name="Apfel", amount="100 g", meal="Frühstück", kcal=52)
    storage.consolidate({"2026-06-20": _day("2026-06-20", [], complete=False)})
    storage.consolidate({"2026-06-20": _day("2026-06-20", [p], complete=True)})
    days = storage.load_days()
    assert len(days["2026-06-20"].products) == 1

    # Unvollstaendiger Import darf vollstaendigen Tag nicht ueberschreiben.
    storage.consolidate({"2026-06-20": _day("2026-06-20", [], complete=False)})
    days = storage.load_days()
    assert len(days["2026-06-20"].products) == 1


def test_product_catalog_and_search():
    p1 = Product(name="Apfel", link="/a", meal="Frühstück", kcal=52)
    p2 = Product(name="Apfel", link="/a", meal="Snacks", kcal=52)
    storage.consolidate({
        "2026-06-20": _day("2026-06-20", [p1]),
        "2026-06-21": _day("2026-06-21", [p2]),
    })
    results = analysis.search_products("apfel")
    assert results[0]["count"] == 2
    assert len(results[0]["dates"]) == 2


def test_aggregations():
    p = Product(name="Reis", meal="Mittagessen", kcal=260, carbs=56)
    storage.consolidate({"2026-06-20": _day("2026-06-20", [p])})
    by_meal = analysis.aggregate_by_meal()
    assert any(g["label"] == "Mittagessen" for g in by_meal)
    by_wd = analysis.aggregate_by_weekday()
    assert by_wd  # nicht leer
    by_month = analysis.aggregate_by_month()
    assert by_month[0]["label"].startswith("Juni")


def test_overview():
    p = Product(name="Reis", meal="Mittagessen", kcal=260)
    storage.consolidate({"2026-06-20": _day("2026-06-20", [p])})
    ov = analysis.overview()
    assert ov["count"] == 1
    assert ov["empty"] is False
