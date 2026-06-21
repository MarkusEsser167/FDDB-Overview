"""Programmstart: lokaler Webserver auf localhost:8080 + Browser-Autostart.

Aufruf:
    python -m fddb_overview
oder als gepackte EXE (siehe scripts/build-portable-windows.ps1).
"""
from __future__ import annotations

import os
import sys
import threading
import webbrowser
from pathlib import Path


def _base_dir() -> Path:
    """Verzeichnis, neben dem der data-Ordner liegt (EXE- oder Skriptpfad)."""
    if getattr(sys, "frozen", False):           # PyInstaller-EXE
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


HOST = os.environ.get("FDDB_HOST", "127.0.0.1")
PORT = int(os.environ.get("FDDB_PORT", "8080"))


def main() -> None:
    # data-Ordner neben der EXE bzw. im Projektordner verankern.
    os.environ.setdefault("FDDB_BASE_DIR", str(_base_dir()))

    import uvicorn
    from .web.app import app

    url = f"http://{HOST}:{PORT}"
    if os.environ.get("FDDB_NO_BROWSER") != "1":
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    print(f"FDDB Overview laeuft unter {url}  (Beenden mit Strg+C)")
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
