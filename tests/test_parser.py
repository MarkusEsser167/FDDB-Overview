"""Tests fuer den FDDB-HTML-Parser und die Zahlenauswertung.

Das Beispiel-HTML bildet die vom Parser genutzte Struktur nach
(Tabelle ``myday-table-std`` mit Produktzeilen, Mahlzeit-Kategoriezeilen,
Summenzeile sowie eine Naehrwertuebersicht fuer Zucker/Ballaststoffe).
"""
from datetime import date

import pytest

from fddb_overview.sync.parser import (parse_diary_day, parse_number,
                                       check_authenticated, FddbAuthError,
                                       FddbParseError)
from bs4 import BeautifulSoup


SAMPLE_HTML = """
<html><body>
<div class="quicklinks"><a class="v2hdlnk" href="#">Abmelden</a></div>
<table class="myday-table-std"><tbody>
  <tr><td colspan="6"><span style="color:#AAAAAA">Frühstück</span></td></tr>
  <tr>
    <td><a href="/db/de/lebensmittel/apfel.html">100 g Apfel roh</a></td>
    <td></td><td>52 kcal</td><td>0,2 g</td><td>14,0 g</td><td>0,3 g</td>
  </tr>
  <tr>
    <td><a href="/db/de/lebensmittel/haferflocken.html">50 g Haferflocken</a></td>
    <td></td><td>185 kcal</td><td>3,5 g</td><td>30,0 g</td><td>6,5 g</td>
  </tr>
  <tr><td colspan="6"><span style="color:#AAAAAA">Mittagessen</span></td></tr>
  <tr>
    <td><a href="/db/de/lebensmittel/reis.html">200 g Reis gekocht</a></td>
    <td></td><td>260 kcal</td><td>0,6 g</td><td>56,0 g</td><td>5,0 g</td>
  </tr>
  <tr class="summe"><td>Summe</td><td></td><td>497 kcal</td>
    <td>4,3 g</td><td>100,0 g</td><td>11,8 g</td></tr>
</tbody></table>

<div id="content"><div></div><div></div>
  <div><div></div>
    <div><div></div>
      <div><div>
        <table></table>
        <table><tbody>
          <tr><td>Kalorien</td><td>497 kcal</td></tr>
          <tr><td>Kohlenhydrate</td><td>100,0 g</td></tr>
          <tr><td>davon Zucker</td><td>18,5 g</td></tr>
          <tr><td>Eiweiß</td><td>11,8 g</td></tr>
          <tr><td>Ballaststoffe</td><td>9,2 g</td></tr>
        </tbody></table>
      </div></div>
    </div>
  </div>
</div>
</body></html>
"""

NOT_LOGGED_IN_HTML = """
<html><body>
<div class="quicklinks"><a class="v2hdlnk" href="#">Anmelden</a></div>
</body></html>
"""


def test_parse_number_german():
    assert parse_number("52 kcal") == 52.0
    assert parse_number("14,0 g") == 14.0
    assert parse_number("1.234,5 kcal") == 1234.5
    assert parse_number("0,3") == 0.3
    assert parse_number("kein Wert") is None


def test_auth_detection():
    soup = BeautifulSoup(NOT_LOGGED_IN_HTML, "lxml")
    with pytest.raises(FddbAuthError):
        check_authenticated(soup)


def test_parse_day_products_and_meals():
    day = parse_diary_day(SAMPLE_HTML, date(2026, 6, 20))
    assert day.date == "2026-06-20"
    assert len(day.products) == 3
    names = [p.name for p in day.products]
    assert "Apfel roh" in names
    assert "Haferflocken" in names
    # Mahlzeit-Zuordnung
    apfel = next(p for p in day.products if "Apfel" in p.name)
    assert apfel.meal == "Frühstück"
    assert apfel.amount == "100 g"
    reis = next(p for p in day.products if "Reis" in p.name)
    assert reis.meal == "Mittagessen"


def test_parse_day_totals():
    day = parse_diary_day(SAMPLE_HTML, date(2026, 6, 20))
    assert day.totals.kcal == pytest.approx(497.0)
    assert day.totals.carbs == pytest.approx(100.0)
    assert day.totals.protein == pytest.approx(11.8)
    assert day.totals.sugar == pytest.approx(18.5)
    assert day.totals.fiber == pytest.approx(9.2)
    assert day.complete is True


def test_no_data_raises():
    with pytest.raises(FddbParseError):
        parse_diary_day("<html><body>nichts</body></html>", date(2026, 6, 20))
