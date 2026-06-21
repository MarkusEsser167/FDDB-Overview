"""HTML-Parser fuer das FDDB-Tagebuch (Seite myday20).

Robuste, label-basierte Auswertung statt fixer XPath-Indizes, damit kleinere
Layout-Aenderungen seitens FDDB nicht sofort alles brechen. Die Grundstruktur
(Tabelle ``myday-table-std`` mit Spalten kcal/Fett/KH/Eiweiss und einer
Summenzeile, Zucker/Ballaststoffe in der Naehrwertuebersicht) folgt der
Beobachtung aus itobey/fddb-exporter.
"""
from __future__ import annotations

import re
from datetime import date
from typing import List, Optional

from bs4 import BeautifulSoup

from ..model.domain import Day, DayTotals, Product


class FddbAuthError(Exception):
    pass


class FddbParseError(Exception):
    pass


# Bekannte Mahlzeitbezeichnungen (DE) zur Gruppierung.
MEAL_KEYWORDS = {
    "frühstück": "Frühstück",
    "fruehstueck": "Frühstück",
    "breakfast": "Frühstück",
    "mittag": "Mittagessen",
    "mittagessen": "Mittagessen",
    "lunch": "Mittagessen",
    "abend": "Abendessen",
    "abendessen": "Abendessen",
    "dinner": "Abendessen",
    "snack": "Snacks",
    "snacks": "Snacks",
    "getränk": "Getränke",
    "getraenk": "Getränke",
    "drinks": "Getränke",
}


def _match_meal(text: str) -> Optional[str]:
    low = text.strip().lower()
    for key, name in MEAL_KEYWORDS.items():
        if key in low:
            return name
    return None


def parse_number(text: str) -> Optional[float]:
    """Liest eine Zahl aus FDDB-Text (deutsches Format, z.B. '1.234,5 kcal')."""
    if text is None:
        return None
    m = re.search(r"-?\d[\d.\s]*(?:,\d+)?|-?\d+(?:\.\d+)?", text.replace("\xa0", " "))
    if not m:
        return None
    token = m.group(0).strip().replace(" ", "")
    if "," in token:                       # deutsches Format: Punkt=Tausender
        token = token.replace(".", "").replace(",", ".")
    else:
        # Nur Punkte: koennten Tausender sein, wenn mehrere/dreistellig.
        if token.count(".") > 1:
            token = token.replace(".", "")
    try:
        return float(token)
    except ValueError:
        return None


def _num(text: str) -> float:
    v = parse_number(text)
    return v if v is not None else 0.0


def check_authenticated(soup: BeautifulSoup) -> None:
    """Wirft FddbAuthError, wenn die Seite einen Login-Link zeigt."""
    for a in soup.select("div.quicklinks a.v2hdlnk"):
        if a.get_text(strip=True) in ("Anmelden", "Login"):
            raise FddbAuthError(
                "Nicht bei FDDB angemeldet - Cookie/Zugangsdaten pruefen."
            )


def _is_category_row(tds) -> Optional[str]:
    """Erkennt eine Kategorie-/Mahlzeit-Zwischenzeile (grauer Text)."""
    for td in tds:
        span = td.find("span", style=True)
        if span and "color:#aaaaaa" in span.get("style", "").replace(" ", "").lower():
            return span.get_text(" ", strip=True)
    return None


def _meal_for_table(table) -> str:
    """Sucht eine Mahlzeitbezeichnung im Umfeld der Tabelle."""
    # Vorausgehende Ueberschriften / Container pruefen.
    node = table
    for _ in range(4):
        node = node.find_previous(
            ["div", "h1", "h2", "h3", "h4", "td", "span", "a"])
        if node is None:
            break
        meal = _match_meal(node.get_text(" ", strip=True)[:60])
        if meal:
            return meal
    return "Sonstiges"


def _parse_product_row(tds, meal: str) -> Optional[Product]:
    if len(tds) < 6:
        return None
    link_el = tds[0].find("a")
    name = ""
    amount = ""
    href = ""
    if link_el is not None:
        href = link_el.get("href", "")
        full = link_el.get_text(" ", strip=True)
        parts = full.split(" ", 2)
        if len(parts) == 3 and re.match(r"^[\d.,]+$", parts[0]):
            amount = f"{parts[0]} {parts[1]}"
            name = parts[2]
        else:
            name = full
    else:
        name = tds[0].get_text(" ", strip=True)
    if not name:
        return None
    return Product(
        name=name,
        amount=amount,
        link=href,
        meal=meal,
        kcal=_num(tds[2].get_text()),
        fat=_num(tds[3].get_text()),
        carbs=_num(tds[4].get_text()),
        protein=_num(tds[5].get_text()),
    )


def _looks_like_total(tds) -> bool:
    text = " ".join(td.get_text(" ", strip=True) for td in tds[:2]).lower()
    return any(w in text for w in ("summe", "gesamt", "total", "tagessumme"))


def _extract_summary_value(soup: BeautifulSoup, *labels: str) -> Optional[float]:
    """Sucht in der Naehrwertuebersicht einen Wert anhand des Labels."""
    targets = [l.lower() for l in labels]
    for tr in soup.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        label = cells[0].get_text(" ", strip=True).lower()
        if any(t in label for t in targets):
            for cell in cells[1:]:
                val = parse_number(cell.get_text(" ", strip=True))
                if val is not None:
                    return val
    return None


def parse_diary_day(html: str, day: date) -> Day:
    """Parst das Tagebuch-HTML eines Tages in ein Day-Objekt."""
    soup = BeautifulSoup(html, "lxml")
    check_authenticated(soup)

    products: List[Product] = []
    tables = soup.select("table.myday-table-std")
    if not tables:
        raise FddbParseError(
            "Keine Tagebuch-Tabelle gefunden - vermutlich keine Daten fuer "
            f"{day.isoformat()} oder veraendertes Seitenlayout."
        )

    for table in tables:
        current_meal = _meal_for_table(table)
        rows = table.find_all("tr")
        for i, row in enumerate(rows):
            tds = row.find_all("td")
            if len(tds) <= 1:
                meal = _match_meal(row.get_text(" ", strip=True))
                if meal:
                    current_meal = meal
                continue
            cat = _is_category_row(tds)
            if cat:
                meal = _match_meal(cat)
                if meal:
                    current_meal = meal
                continue
            if _looks_like_total(tds):
                continue
            product = _parse_product_row(tds, current_meal)
            if product:
                products.append(product)

    totals = DayTotals(
        kcal=round(sum(p.kcal for p in products), 1),
        fat=round(sum(p.fat for p in products), 1),
        carbs=round(sum(p.carbs for p in products), 1),
        protein=round(sum(p.protein for p in products), 1),
        sugar=_extract_summary_value(soup, "zucker", "sugar"),
        fiber=_extract_summary_value(soup, "ballaststoff", "fibre", "fiber"),
    )

    return Day(
        date=day.isoformat(),
        products=products,
        totals=totals,
        complete=len(products) > 0,
    )
