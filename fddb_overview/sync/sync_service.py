"""Orchestriert den FDDB-Sync ueber einen Zeitraum inkl. Fortschritt.

Ablauf:
  1. Login/Session sicherstellen
  2. je Tag HTML laden und parsen
  3. Snapshot schreiben
  4. in die konsolidierte Arbeitsdatei einpflegen
"""
from __future__ import annotations

import threading
from datetime import date, timedelta
from typing import Dict, Optional

from .. import storage
from ..model.domain import Day
from .fddb_client import FddbClient, FddbAuthError, daterange, parse_iso
from .parser import parse_diary_day, FddbAuthError as ParseAuthError, FddbParseError


class SyncProgress:
    """Thread-sicherer Fortschrittsstatus fuer die Oberflaeche."""

    def __init__(self):
        self._lock = threading.Lock()
        self.running = False
        self.total = 0
        self.done = 0
        self.current = ""
        self.message = ""
        self.error = ""
        self.finished = False
        self.imported_days = 0

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "running": self.running,
                "total": self.total,
                "done": self.done,
                "current": self.current,
                "message": self.message,
                "error": self.error,
                "finished": self.finished,
                "imported_days": self.imported_days,
            }

    def update(self, **kw):
        with self._lock:
            for k, v in kw.items():
                setattr(self, k, v)


# Globaler Fortschritt (eine Sync-Operation gleichzeitig).
progress = SyncProgress()


def suggest_timeframe() -> Dict[str, str]:
    """Schlaegt einen Zeitraum vor (wie im Original).

    - gibt es unvollstaendige Tage: vom aeltesten unvollstaendigen Tag bis heute
    - sonst: heute minus 14 Tage bis heute
    """
    days = storage.load_days()
    today = date.today()
    incomplete = sorted(d for d, day in days.items() if not day.complete)
    if incomplete:
        start = parse_iso(incomplete[0])
    else:
        start = today - timedelta(days=14)
    return {"from": start.isoformat(), "to": today.isoformat()}


def run_sync(from_iso: str, to_iso: str,
             username: str = "", password: str = "", cookie: str = "") -> dict:
    """Fuehrt den Sync synchron aus und gibt eine Zusammenfassung zurueck."""
    start = parse_iso(from_iso)
    end = parse_iso(to_iso)
    if end < start:
        start, end = end, start

    settings = storage.load_settings()
    username = username or settings.get("fddb_username", "")
    password = password or settings.get("fddb_password", "")
    cookie = cookie or settings.get("fddb_cookie", "")

    total = (end - start).days + 1
    progress.update(running=True, total=total, done=0, error="",
                    finished=False, imported_days=0, message="Anmeldung ...")

    new_days: Dict[str, Day] = {}
    try:
        with FddbClient(username=username, password=password, cookie=cookie) as client:
            client.ensure_session()
            for d in daterange(start, end):
                progress.update(current=d.isoformat(),
                                message=f"Lade {d.isoformat()} ...")
                try:
                    html = client.fetch_day_html(d)
                    day = parse_diary_day(html, d)
                    new_days[d.isoformat()] = day
                    progress.update(imported_days=len(new_days))
                except FddbParseError:
                    # Tag ohne Daten -> als leeren, unvollstaendigen Tag merken.
                    pass
                except (FddbAuthError, ParseAuthError) as exc:
                    raise FddbAuthError(str(exc))
                finally:
                    progress.update(done=progress.snapshot()["done"] + 1)
    except (FddbAuthError, ParseAuthError) as exc:
        progress.update(running=False, finished=True, error=str(exc))
        return {"ok": False, "error": str(exc)}
    except Exception as exc:  # netzwerk o.ae.
        progress.update(running=False, finished=True, error=str(exc))
        return {"ok": False, "error": str(exc)}

    if new_days:
        storage.write_snapshot(new_days, {
            "from": from_iso, "to": to_iso, "days": len(new_days),
        })
        storage.consolidate(new_days)

    progress.update(running=False, finished=True,
                    message=f"{len(new_days)} Tage importiert.")
    return {"ok": True, "imported_days": len(new_days),
            "from": from_iso, "to": to_iso}


def run_sync_async(from_iso: str, to_iso: str, **creds) -> None:
    """Startet den Sync in einem Hintergrund-Thread."""
    t = threading.Thread(target=run_sync, args=(from_iso, to_iso),
                         kwargs=creds, daemon=True)
    t.start()
