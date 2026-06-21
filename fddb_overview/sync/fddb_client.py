"""HTTP-Zugriff auf fddb.info: Login (Passwort) bzw. Cookie + Tagebuch-Abruf.

Die Mechanik ist aus dem quelloffenen Projekt itobey/fddb-exporter rekonstruiert:

  * Login:  POST /db/i18n/account/?lang=de&action=login
            Felder: loginemailorusername, loginpassword
            -> Set-Cookie:  fddb=<wert>
  * Tagebuch (je Tag):
            GET  /db/i18n/myday20/?lang=de&q=<to>&p=<from>
            Header: Cookie: fddb=<wert>  (+ optional Basic-Auth)
            p/q sind Unix-Zeitstempel (Sekunden) fuer Tagesanfang/-ende.
"""
from __future__ import annotations

import base64
from datetime import date, datetime, time, timedelta
from typing import Optional

import httpx

BASE_URL = "https://fddb.info"
LOGIN_PATH = "/db/i18n/account/?lang=de&action=login"
DIARY_PATH = "/db/i18n/myday20/"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class FddbAuthError(Exception):
    """Login fehlgeschlagen oder Sitzung ungueltig."""


class FddbClient:
    """Kapselt Login und Tagebuch-Abruf gegen fddb.info."""

    def __init__(self, username: str = "", password: str = "",
                 cookie: str = "", timeout: float = 30.0):
        self.username = username.strip()
        self.password = password
        self.cookie = cookie.strip()
        self._client = httpx.Client(
            base_url=BASE_URL,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "de-DE,de;q=0.9"},
        )

    # -- Kontextmanager -----------------------------------------------------
    def __enter__(self) -> "FddbClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    # -- Login --------------------------------------------------------------
    def ensure_session(self) -> str:
        """Stellt sicher, dass ein gueltiges fddb-Cookie vorliegt.

        Bevorzugt ein manuell hinterlegtes Cookie; sonst Login per Passwort.
        Gibt das Cookie zurueck.
        """
        if self.cookie:
            return self.cookie
        if self.username and self.password:
            self.cookie = self._login()
            return self.cookie
        raise FddbAuthError(
            "Keine Zugangsdaten: Bitte FDDB-Benutzername/Passwort oder ein "
            "fddb-Cookie in den Einstellungen hinterlegen."
        )

    def _login(self) -> str:
        try:
            resp = self._client.post(
                LOGIN_PATH,
                data={
                    "loginemailorusername": self.username,
                    "loginpassword": self.password,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except httpx.HTTPError as exc:
            raise FddbAuthError(f"Login-Anfrage fehlgeschlagen: {exc}") from exc

        # Cookie aus dem Client-Jar oder aus Set-Cookie lesen.
        cookie = self._client.cookies.get("fddb")
        if cookie:
            return cookie
        for raw in resp.headers.get_list("set-cookie") if hasattr(
                resp.headers, "get_list") else []:
            if raw.startswith("fddb="):
                return raw.split(";")[0][len("fddb="):]
        raise FddbAuthError(
            "Login zu FDDB nicht erfolgreich - bitte Zugangsdaten pruefen."
        )

    # -- Tagebuch -----------------------------------------------------------
    def fetch_day_html(self, day: date) -> str:
        """Laedt das Tagebuch-HTML fuer einen einzelnen Tag."""
        cookie = self.ensure_session()
        start = int(datetime.combine(day, time.min).timestamp())
        end = int(datetime.combine(day, time.max).timestamp())

        headers = {"Cookie": f"fddb={cookie}"}
        if self.username and self.password:
            auth = base64.b64encode(
                f"{self.username}:{self.password}".encode("utf-8")
            ).decode("ascii")
            headers["Authorization"] = f"Basic {auth}"

        resp = self._client.get(
            DIARY_PATH,
            params={"lang": "de", "q": end, "p": start},
            headers=headers,
        )
        resp.raise_for_status()
        return resp.text


def daterange(start: date, end: date):
    """Erzeugt alle Tage von start bis end (inklusive)."""
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def parse_iso(d: str) -> date:
    return datetime.strptime(d, "%Y-%m-%d").date()
