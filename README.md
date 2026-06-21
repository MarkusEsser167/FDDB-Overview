# FDDB Overview

Lokales Webtool zur Auswertung von Ernährungsdaten aus **[FDDB.info](https://fddb.info/)**.
Das Tool meldet sich bei FDDB an, liest das Ernährungstagebuch aus, erzeugt daraus
konsolidierte `days.json`/`products.json` und bietet Tagesauswertungen, Listen,
Verdichtungen sowie Excel- und PDF-Export.

Funktional ist es an [danizwam/yazio-overview](https://github.com/danizwam/yazio-overview)
angelehnt, greift aber statt auf Yazio auf FDDB zu. Da FDDB **keine offene API**
anbietet, wird das Ernährungstagebuch über die normale Website ausgelesen
(Ansatz wie bei [itobey/fddb-exporter](https://github.com/itobey/fddb-exporter)).

## Schnellstart (ohne Installation)

1. Portable ZIP herunterladen (GitHub Release oder Actions-Artefakt)
2. ZIP entpacken
3. `FDDB Overview.exe` starten
4. Der Browser öffnet sich automatisch unter <http://localhost:8080>

Die lokalen Daten liegen neben der EXE im Ordner `data`. Der komplette Ordner
lässt sich kopieren oder auf einen anderen Rechner verschieben.

## Lokaler Start mit Python

Voraussetzung: Python 3.11+.

```bash
pip install -r requirements.txt
python -m fddb_overview
```

Danach ist die Oberfläche unter <http://localhost:8080> erreichbar.

Optional lässt sich der Datenordner überschreiben:

```bash
# Windows (PowerShell)
$env:FDDB_DATA_DIR = "C:\fddb-data"
python -m fddb_overview
```

## Portable Windows-Version selbst bauen

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-portable-windows.ps1
```

Ergebnis:

```
dist\FDDB Overview\FDDB Overview.exe
dist\FDDB-Overview-Windows-Portable.zip
```

## Einrichtung des FDDB-Zugangs

Unter **Einstellungen** in der Oberfläche eine der beiden Varianten hinterlegen:

- **Benutzername + Passwort** – das Tool führt den Login selbst aus.
- **fddb-Cookie** – im Browser bei fddb.info einloggen, Entwicklertools (F12)
  öffnen, unter *Anwendung → Cookies* den Wert des Cookies `fddb` kopieren und
  einfügen. Diese Variante ist robuster gegenüber Layout-Änderungen der
  Login-Seite.

Beides wird ausschließlich lokal in `data/settings.json` gespeichert.

## Funktionen

- Direkter FDDB-Sync per Zeitraum (Login per Passwort **oder** Cookie)
- Manueller JSON-Import (`days.json`) für Backups/Reparaturen
- Inkrementelle Import-Snapshots mit konsolidierter Arbeitsdatei
- Einzelner Tag mit Mahlzeiten, Bestandteilen und Makros
- Datumsbereich mit kopierbaren Tages- und Mahlzeitentexten
- Tagesnotizen für „Besonderheiten an diesem Tag"
- Profilinformationen (Name, Geburtsdatum) in Excel/PDF
- Listenansicht mit Produktsuche, Wochentagsfilter, Top-100 und Tagesranking
- Verdichtungen nach Mahlzeit, Wochentag und Monat
- Verlinkung von Listen auf Produkt-Verzehrtage bzw. Tagesübersicht
- Excel-Export (ein Tabellenblatt pro Tag) und PDF-Export für Tag/Bereich
- Hilfeseite und Einstiegshinweis bei leerem Datenbestand
- Responsive Weboberfläche ohne externe JS-Abhängigkeiten

## Datenhaltung

```
data/days.json                       konsolidierte Tagesdaten
data/products.json                   abgeleiteter Produktkatalog
data/imports/<zeitstempel>/days.json einzelne Import-Snapshots
data/imports/<zeitstempel>/metadata.json
data/settings.json                   Profil + FDDB-Zugangsdaten
data/notes.json                      Tagesnotizen
```

Bei sich überschneidenden Tagen gilt: vollständige Tage schlagen unvollständige;
bei gleicher Qualität gewinnt der spätere Import.

## Code-Struktur

```
fddb_overview/
  __main__.py          Start: Webserver + Browser-Autostart
  storage.py           JSON-Datenhaltung, Snapshots, Konsolidierung
  model/domain.py      Domain-Modelle und Anzeigeformatierung
  sync/                FDDB-Login (Passwort/Cookie) + Tagebuch-Parser + Orchestrierung
  service/analysis.py  Tag, Datumsbereich, Listen, Aggregationen
  export/              Excel- und PDF-Export
  web/                 FastAPI-Server + Oberfläche (HTML/CSS/JS)
tests/                 Parser- und Auswertungs-Tests
scripts/               Build-Skript für die portable Windows-Version
```

## Tests

```bash
python -m pytest tests/ -q
```

## Hinweis

FDDB.info bietet keine offizielle API. Dieses Tool liest die Daten über die
Website aus. Ändert FDDB das Seitenlayout, kann eine Anpassung der Auslesung in
`fddb_overview/sync/parser.py` nötig werden. Die Zugangsdaten verlassen den
lokalen Rechner nicht.

## Lizenz

MIT
