"""Exports de trésorerie (S3 / US-35) : Excel 8 colonnes et rappels ICS, d'origine, par salarié.

- Excel : chaque feuille est produite par ``legacy.rapport.build_recap_xlsx`` d'origine (8 colonnes,
  styles, ``#,##0 "DH"``, ligne TOTAL, filtres, volets figés). Un seul salarié : fichier d'origine
  tel quel. Plusieurs : une feuille par salarié, recopiée cellule par cellule (valeurs, styles,
  largeurs, filtre, volets) dans un même classeur.
- ICS : ``legacy.rapport.build_ics`` d'origine, événements de tous les salariés dans un calendrier ;
  le nom du salarié est ajouté à l'intitulé, et l'UID inclut le matricule (unicité entre salariés).
- Noms de fichiers d'origine : recap_paiements.xlsx, base_complete.xlsx, rappels_salaires_cnss.ics.
"""

from __future__ import annotations

import uuid
from copy import copy
from io import BytesIO

from openpyxl import Workbook, load_workbook

from app.paie.core.models.entities import Employee
from app.tresorerie.legacy import rapport

FILE_RECAP = "recap_paiements.xlsx"
FILE_COMPLETE = "base_complete.xlsx"
FILE_ICS = "rappels_salaires_cnss.ics"


def _sheet_title(emp: Employee, used: set[str]) -> str:
    base = f"{emp.matricule} {emp.nom}".replace("/", "-").replace("\\", "-")
    for ch in "[]:*?":
        base = base.replace(ch, "")
    title, i = base[:31], 2
    while title in used:
        suffix = f" ({i})"
        title, i = base[:31 - len(suffix)] + suffix, i + 1
    used.add(title)
    return title


def _copy_sheet(src, dst) -> None:
    for row in src.iter_rows():
        for cell in row:
            new = dst.cell(row=cell.row, column=cell.column, value=cell.value)
            if cell.has_style:
                new.font, new.fill, new.border = copy(cell.font), copy(cell.fill), copy(cell.border)
                new.alignment, new.number_format = copy(cell.alignment), cell.number_format
                new.protection = copy(cell.protection)
    for key, dim in src.column_dimensions.items():
        dst.column_dimensions[key].width = dim.width
    dst.freeze_panes = src.freeze_panes
    dst.auto_filter.ref = src.auto_filter.ref


def build_recap_xlsx(groups: list[tuple[Employee, list[dict]]], only_paid: bool) -> bytes:
    if len(groups) == 1:
        return rapport.build_recap_xlsx(groups[0][1], only_paid=only_paid)
    wb, used = Workbook(), set()
    wb.remove(wb.active)
    for emp, records in groups:
        src = load_workbook(BytesIO(rapport.build_recap_xlsx(records, only_paid=only_paid))).active
        _copy_sheet(src, wb.create_sheet(_sheet_title(emp, used)))
    if not wb.sheetnames:
        wb.create_sheet("Recap" if only_paid else "Complet")
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _unfold(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.split("\r\n"):
        if raw.startswith(" ") and lines:
            lines[-1] += raw[1:]
        elif raw:
            lines.append(raw)
    return lines


def _events(ics: str, emp: Employee) -> list[str]:
    """Événements d'un calendrier d'origine, intitulé préfixé du salarié, UID incluant le matricule."""
    name = rapport._esc(f"{emp.prenom} {emp.nom}".strip())
    out, inside = [], False
    for line in _unfold(ics):
        if line == "BEGIN:VEVENT":
            inside = True
        if not inside:
            continue
        if line.startswith("SUMMARY:"):
            line = f"SUMMARY:{name} · " + line[len("SUMMARY:"):]
        elif line.startswith("DESCRIPTION:Rappel J-1 — "):
            line = f"DESCRIPTION:Rappel J-1 — {name} · " + line[len("DESCRIPTION:Rappel J-1 — "):]
        out.append(line)
        if line == "END:VEVENT":
            inside = False
    # UID : uuid5(matricule + date + intitulé d'origine), stable d'un export à l'autre.
    result, block = [], []
    for line in out:
        block.append(line)
        if line == "END:VEVENT":
            key = emp.matricule + "|" + next(l for l in block if l.startswith("DTSTART")) + "|" + \
                next(l for l in block if l.startswith("SUMMARY:"))
            block = [f"UID:{uuid.uuid5(uuid.NAMESPACE_DNS, key)}@hbn-paie" if l.startswith("UID:") else l
                     for l in block]
            result += block
            block = []
    return [rapport._fold(l) for l in result]


def build_ics(groups: list[tuple[Employee, list[dict]]], only_unpaid: bool = True) -> bytes:
    header = _unfold(rapport.build_ics([], only_unpaid=only_unpaid).decode("utf-8"))
    head = [l for l in header if l != "END:VCALENDAR"]
    events: list[str] = []
    for emp, records in groups:
        events += _events(rapport.build_ics(records, only_unpaid=only_unpaid).decode("utf-8"), emp)
    return ("\r\n".join(head + events + ["END:VCALENDAR"]) + "\r\n").encode("utf-8")
