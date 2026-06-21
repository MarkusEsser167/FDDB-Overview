"""PDF-Export fuer einen Tag oder einen Datumsbereich."""
from __future__ import annotations

import io
from typing import List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from .. import storage
from ..service import analysis

_GREEN = colors.HexColor("#2E5E3A")
_LIGHT = colors.HexColor("#D7E8DC")


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("DayTitle", parent=s["Heading2"], textColor=_GREEN))
    s.add(ParagraphStyle("Small", parent=s["Normal"], fontSize=8,
                         textColor=colors.HexColor("#555555")))
    return s


def _day_flow(day_view: dict, profile: dict, styles) -> list:
    flow = []
    flow.append(Paragraph(
        f"{day_view['date']} ({day_view['weekday']})", styles["DayTitle"]))
    meta = []
    if profile.get("name"):
        meta.append("Profil: " + profile["name"]
                    + (f", geb. {profile['birthdate']}" if profile.get("birthdate") else ""))
    if day_view.get("note"):
        meta.append("Besonderheiten: " + day_view["note"])
    if meta:
        flow.append(Paragraph(" &nbsp;|&nbsp; ".join(meta), styles["Small"]))
    flow.append(Spacer(1, 0.2 * cm))

    data = [["Mahlzeit", "Menge", "Produkt", "kcal", "Fett", "KH", "EW"]]
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), _GREEN),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CCCCCC")),
        ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    r = 1
    for meal in day_view["meals"]:
        for p in meal["products"]:
            data.append([meal["name"], p["amount"], p["name"],
                         _fmt(p["kcal"]), _fmt(p["fat"]),
                         _fmt(p["carbs"]), _fmt(p["protein"])])
            r += 1
        data.append([f"{meal['name']} gesamt", "", "", _fmt(meal["kcal"]),
                     _fmt(meal["fat"]), _fmt(meal["carbs"]), _fmt(meal["protein"])])
        style_cmds.append(("BACKGROUND", (0, r), (-1, r), _LIGHT))
        style_cmds.append(("FONTNAME", (0, r), (-1, r), "Helvetica-Bold"))
        r += 1

    t = day_view["totals"]
    data.append(["Tagessumme", "", "", _fmt(t.get("kcal")), _fmt(t.get("fat")),
                 _fmt(t.get("carbs")), _fmt(t.get("protein"))])
    style_cmds.append(("FONTNAME", (0, r), (-1, r), "Helvetica-Bold"))
    style_cmds.append(("LINEABOVE", (0, r), (-1, r), 1, _GREEN))

    table = Table(data, colWidths=[2.6 * cm, 2 * cm, 6.5 * cm, 1.6 * cm,
                                    1.5 * cm, 1.5 * cm, 1.5 * cm], repeatRows=1)
    table.setStyle(TableStyle(style_cmds))
    flow.append(table)

    extra = []
    if t.get("sugar") is not None:
        extra.append(f"davon Zucker: {t['sugar']} g")
    if t.get("fiber") is not None:
        extra.append(f"Ballaststoffe: {t['fiber']} g")
    if extra:
        flow.append(Spacer(1, 0.15 * cm))
        flow.append(Paragraph("   ".join(extra), styles["Small"]))
    return flow


def _fmt(v) -> str:
    if v is None:
        return ""
    return f"{round(float(v), 1):g}".replace(".", ",")


def export_days(date_isos: List[str]) -> bytes:
    profile = storage.load_settings()
    styles = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=1.5 * cm,
                            bottomMargin=1.5 * cm, leftMargin=1.5 * cm,
                            rightMargin=1.5 * cm, title="FDDB Auswertung")
    flow = []
    if not date_isos:
        flow.append(Paragraph("Keine Daten fuer den gewaehlten Zeitraum.",
                              styles["Normal"]))
    for i, iso in enumerate(date_isos):
        day_view = analysis.get_day(iso)
        if day_view is None:
            continue
        if i > 0:
            flow.append(Spacer(1, 0.6 * cm))
        flow.extend(_day_flow(day_view, profile, styles))
    doc.build(flow)
    return buf.getvalue()


def export_single_day(date_iso: str) -> bytes:
    return export_days([date_iso])


def export_range(from_iso: str, to_iso: str) -> bytes:
    rng = analysis.get_range(from_iso, to_iso)
    return export_days([d["date"] for d in rng["days"]])
