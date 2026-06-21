"""Domain-Modelle und Anzeigeformatierung.

Die Daten werden als einfache Dictionaries gehalten, damit sie ohne
Konvertierung als JSON gespeichert und im Browser verwendet werden koennen.
Diese Klassen kapseln nur Erzeugung und Formatierung.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


# Reihenfolge der Mahlzeiten fuer eine stabile Sortierung in der Oberflaeche.
MEAL_ORDER = [
    "Fruehstueck",
    "Frühstück",
    "Mittagessen",
    "Abendessen",
    "Snacks",
    "Getraenke",
    "Getränke",
    "Sonstiges",
]


def meal_sort_key(name: str) -> int:
    """Liefert die Sortierposition einer Mahlzeit (unbekannte ans Ende)."""
    try:
        return MEAL_ORDER.index(name)
    except ValueError:
        return len(MEAL_ORDER)


@dataclass
class Product:
    """Ein einzelner Eintrag im Tagebuch (verzehrtes Lebensmittel)."""

    name: str = ""
    amount: str = ""          # z.B. "100 g" oder "1 Portion"
    link: str = ""            # Produktseite auf fddb.info
    meal: str = "Sonstiges"   # zugeordnete Mahlzeit
    kcal: float = 0.0
    fat: float = 0.0
    carbs: float = 0.0
    protein: float = 0.0
    sugar: Optional[float] = None
    fiber: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Product":
        return Product(
            name=d.get("name", ""),
            amount=d.get("amount", ""),
            link=d.get("link", ""),
            meal=d.get("meal", "Sonstiges"),
            kcal=float(d.get("kcal", 0) or 0),
            fat=float(d.get("fat", 0) or 0),
            carbs=float(d.get("carbs", 0) or 0),
            protein=float(d.get("protein", 0) or 0),
            sugar=_opt_float(d.get("sugar")),
            fiber=_opt_float(d.get("fiber")),
        )


@dataclass
class DayTotals:
    kcal: float = 0.0
    fat: float = 0.0
    carbs: float = 0.0
    protein: float = 0.0
    sugar: Optional[float] = None
    fiber: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Day:
    """Ein Tag mit allen Eintraegen, gruppiert nach Mahlzeiten."""

    date: str = ""                       # ISO-Format YYYY-MM-DD
    products: list = field(default_factory=list)  # list[Product]
    totals: DayTotals = field(default_factory=DayTotals)
    complete: bool = True                # vollstaendig importiert?

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "products": [p.to_dict() for p in self.products],
            "totals": self.totals.to_dict(),
            "complete": self.complete,
        }

    @staticmethod
    def from_dict(d: dict) -> "Day":
        totals = d.get("totals", {}) or {}
        return Day(
            date=d.get("date", ""),
            products=[Product.from_dict(p) for p in d.get("products", [])],
            totals=DayTotals(
                kcal=float(totals.get("kcal", 0) or 0),
                fat=float(totals.get("fat", 0) or 0),
                carbs=float(totals.get("carbs", 0) or 0),
                protein=float(totals.get("protein", 0) or 0),
                sugar=_opt_float(totals.get("sugar")),
                fiber=_opt_float(totals.get("fiber")),
            ),
            complete=bool(d.get("complete", True)),
        )

    def meals(self) -> list:
        """Gruppiert die Eintraege nach Mahlzeit und sortiert sie."""
        groups: dict = {}
        for p in self.products:
            groups.setdefault(p.meal, []).append(p)
        result = []
        for meal in sorted(groups.keys(), key=meal_sort_key):
            items = groups[meal]
            result.append({
                "name": meal,
                "products": [p.to_dict() for p in items],
                "kcal": round(sum(p.kcal for p in items), 1),
                "fat": round(sum(p.fat for p in items), 1),
                "carbs": round(sum(p.carbs for p in items), 1),
                "protein": round(sum(p.protein for p in items), 1),
            })
        return result


def _opt_float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
